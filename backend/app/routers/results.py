import io
import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import ExamAttempt, StudentApplication, Candidate, Course, Admin, Exam, Question
from app.schemas import CourseRankingEntry
from app.auth import get_current_admin, get_current_candidate
from app.utils.community import normalize_community, get_community_display

router = APIRouter(prefix="/api/v1/results", tags=["Results & Rankings"])


def get_course_rankings_internal(
    db: Session,
    course_code: str,
    search: Optional[str] = None,
    community: Optional[str] = None,
    show_excluded: bool = False
) -> List[dict]:
    # 1. Fetch Course
    course = db.query(Course).filter(Course.code == course_code.upper()).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with code '{course_code}' not found."
        )

    # 2. Fetch all student applications for this course with submitted attempts
    apps = db.query(StudentApplication, Candidate, ExamAttempt).join(
        Candidate, StudentApplication.candidate_id == Candidate.id
    ).join(
        ExamAttempt, ExamAttempt.candidate_id == Candidate.id
    ).filter(
        StudentApplication.course_id == course.id,
        ExamAttempt.is_submitted == True,
        StudentApplication.is_active == True
    ).all()

    # Load all questions to compute marks map
    all_questions = db.query(Question.id, Question.marks).all()
    q_marks_map = {q.id: q.marks for q in all_questions}

    # 3. Calculate components and build candidates list
    candidates_data = []
    for app_rec, candidate, attempt in apps:
        is_incomplete_ug = (app_rec.ug_marks is None or app_rec.ug_marks < 0.0 or app_rec.ug_marks > 100.0)
        
        # Calculate dynamic total marks from attempt question order
        total_marks = 100.0
        if attempt.question_order_json:
            try:
                import json
                order_data = json.loads(attempt.question_order_json)
                final_order = order_data.get("final_order", [])
                if final_order:
                    total_marks = sum(q_marks_map.get(qid, 1.0) for qid in final_order)
            except Exception:
                pass
        if total_marks <= 0:
            total_marks = float(attempt.total_questions) if attempt.total_questions else 100.0

        entrance_percentage = max(0.0, min(100.0, (attempt.score / total_marks) * 100))
        entrance_weighted_score = entrance_percentage * 0.50

        if is_incomplete_ug:
            ug_percentage = None
            ug_weighted_score = None
            final_score = None
            is_excluded = True
            excluded_reason = "Incomplete UG Percentage"
        else:
            ug_percentage = max(0.0, min(100.0, app_rec.ug_marks))
            ug_weighted_score = ug_percentage * 0.50
            final_score = round(entrance_weighted_score + ug_weighted_score, 2)
            final_score = max(0.0, min(100.0, final_score))

            is_excluded = candidate.admitted_course_id is not None and candidate.admitted_course_id != course.id
            excluded_reason = None
            if is_excluded:
                adm_course = db.query(Course).filter(Course.id == candidate.admitted_course_id).first()
                excluded_reason = f"Admitted to {adm_course.code}" if adm_course else "Admitted to another course"

        candidates_data.append({
            "app_rec": app_rec,
            "candidate": candidate,
            "attempt": attempt,
            "entrance_score": attempt.score,
            "entrance_total_marks": total_marks,
            "entrance_percentage": entrance_percentage,
            "entrance_weighted_score": entrance_weighted_score,
            "ug_percentage": ug_percentage,
            "ug_weighted_score": ug_weighted_score,
            "final_score": final_score,
            "is_excluded": is_excluded,
            "excluded_reason": excluded_reason,
            "submitted_at": attempt.submitted_at,
            "candidate_id": candidate.id
        })

    # 4. Sort strictly using the 5-layer tie-breaker key
    # (final_score desc -> entrance_percentage desc -> ug_percentage desc -> submitted_at asc -> candidate_id asc)
    # Candidates with missing final score are sorted to the bottom using -2.0
    def sort_key(item):
        fs = item["final_score"] if item["final_score"] is not None else -2.0
        ep = item["entrance_percentage"] if item["entrance_percentage"] is not None else -2.0
        up = item["ug_percentage"] if item["ug_percentage"] is not None else -2.0
        sat = item["submitted_at"] or datetime.datetime.max
        cid = item["candidate_id"]
        return (-fs, -ep, -up, sat, cid)

    candidates_data.sort(key=sort_key)

    # 5. Compute original rank (ranking based on final_score)
    current_orig_rank = 1
    for idx, item in enumerate(candidates_data):
        if item["final_score"] is None:
            item["orig_rank"] = -1
            continue
        if idx > 0 and candidates_data[idx - 1]["final_score"] is not None and item["final_score"] < candidates_data[idx - 1]["final_score"]:
            current_orig_rank = idx + 1
        item["orig_rank"] = current_orig_rank

    # Load community seats
    from app.models import CourseCommunitySeat
    course_seats = db.query(CourseCommunitySeat).filter(CourseCommunitySeat.course_id == course.id).all()
    seat_limits = {s.community_code: s.seat_count for s in course_seats}
    for code in ["OC", "BC", "BCM", "MBC", "SC", "SCA", "ST"]:
        if code not in seat_limits:
            seat_limits[code] = 0

    remaining = seat_limits.copy()

    # Compute overall active rank and open_competition_rank for all active candidates based on final_score
    active_idx = 0
    last_active_score = None
    last_active_rank = 1
    for item in candidates_data:
        if not item["is_excluded"]:
            active_idx += 1
            if last_active_score is not None and item["final_score"] < last_active_score:
                last_active_rank = active_idx
            item["active_rank"] = last_active_rank
            item["open_competition_rank"] = last_active_rank
            last_active_score = item["final_score"]
        else:
            item["active_rank"] = -1
            item["open_competition_rank"] = -1

    # Allocate OC seats first from overall merit list across all communities using final_score
    for item in candidates_data:
        if not item["is_excluded"]:
            if remaining.get("OC", 0) > 0:
                item["bucket_code"] = "OC"
                item["bucket_name"] = "OC / Open Competition"
                item["community_eligibility_status"] = "Eligible"
                remaining["OC"] -= 1
            else:
                item["bucket_code"] = None

    # Allocate remaining candidates under community quota using final_score
    comm_counters = {code: 0 for code in ["BC", "BCM", "MBC", "SC", "SCA", "ST", "OC_SEAT"]}
    comm_last_score = {code: None for code in ["BC", "BCM", "MBC", "SC", "SCA", "ST", "OC_SEAT"]}
    comm_last_rank = {code: 1 for code in ["BC", "BCM", "MBC", "SC", "SCA", "ST", "OC_SEAT"]}

    final_list = []
    for item in candidates_data:
        normalized_c = normalize_community(item["app_rec"].community)
        
        if normalized_c not in comm_counters:
            comm_counters[normalized_c] = 0
        if normalized_c not in comm_last_score:
            comm_last_score[normalized_c] = None
            comm_last_rank[normalized_c] = 1
        if normalized_c not in seat_limits:
            seat_limits[normalized_c] = 0
            remaining[normalized_c] = 0

        excluded_reason = item["excluded_reason"]

        if item["is_excluded"]:
            bucket_code = normalized_c
            if bucket_code == "OC_SEAT":
                bucket_code = "OC"
            bucket_name = get_community_display(bucket_code, course.code)
            comm_rank = -1
            community_eligibility_status = "Excluded"
            if excluded_reason == "Incomplete UG Percentage":
                community_eligibility_status = "Incomplete UG Percentage"
            is_eligible = False
        else:
            if item.get("bucket_code") == "OC":
                comm_rank = -1
                bucket_code = "OC"
                bucket_name = "OC / Open Competition"
                community_eligibility_status = "Eligible"
                is_eligible = True
            else:
                comm_counters[normalized_c] += 1
                if comm_last_score[normalized_c] is not None and item["final_score"] < comm_last_score[normalized_c]:
                    comm_last_rank[normalized_c] = comm_counters[normalized_c]
                comm_rank = comm_last_rank[normalized_c]
                comm_last_score[normalized_c] = item["final_score"]

                if normalized_c == "OC_SEAT":
                    bucket_code = "OC"
                    bucket_name = "OC / Open Competition"
                    if remaining.get("OC", 0) > 0:
                        remaining["OC"] -= 1
                        community_eligibility_status = "Eligible"
                        is_eligible = True
                    else:
                        community_eligibility_status = "Waitlisted"
                        is_eligible = False
                else:
                    bucket_code = normalized_c
                    bucket_name = get_community_display(normalized_c, course.code)
                    if remaining.get(normalized_c, 0) > 0:
                        remaining[normalized_c] -= 1
                        community_eligibility_status = "Eligible"
                        is_eligible = True
                    else:
                        community_eligibility_status = "Waitlisted"
                        is_eligible = False

        degrees = [ap.course.code for ap in item["candidate"].applications]

        if item["candidate"].admitted_course_id == course.id:
            confirmation_status = "Confirmed"
        elif item["is_excluded"]:
            if excluded_reason == "Incomplete UG Percentage":
                confirmation_status = "Incomplete UG Percentage"
            else:
                confirmation_status = "Excluded"
        elif is_eligible:
            confirmation_status = "Eligible"
        else:
            confirmation_status = "Waitlisted"

        display_community = get_community_display(normalized_c, course.code)

        if item["final_score"] is None:
            breakdown_text = "Incomplete UG Percentage"
        else:
            breakdown_text = (
                f"Entrance Mark: {item['entrance_score']} / {item['entrance_total_marks']} | "
                f"Entrance 50%: {item['entrance_weighted_score']:.2f} | "
                f"UG Percentage: {item['ug_percentage']}% | "
                f"UG 50%: {item['ug_weighted_score']:.2f} | "
                f"Final Score: {item['final_score']:.2f} / 100"
            )

        entry = {
            "rank": item["active_rank"] if not item["is_excluded"] else item["orig_rank"],
            "original_rank": item["orig_rank"],
            "active_rank": item["active_rank"],
            "id": item["attempt"].id,
            "candidate_id": item["candidate"].id,
            "application_number": item["app_rec"].application_number,
            "student_name": item["app_rec"].full_name,
            "degrees": degrees,
            "community": item["app_rec"].community or "OC",
            "raw_community": item["app_rec"].community or "OC",
            "normalized_community": display_community,
            "normalized_community_code": normalized_c,
            "open_competition_rank": item["open_competition_rank"],
            "community_rank": comm_rank,
            "community_seat_count": seat_limits.get(normalized_c, 0) if normalized_c != "OC_SEAT" else seat_limits.get("OC", 0),
            "final_selection_bucket_code": bucket_code,
            "final_selection_bucket_name": bucket_name,
            "community_eligibility_status": community_eligibility_status,
            "ug_percentage": item["ug_percentage"],
            "score": item["attempt"].score,
            "percentage": item["attempt"].percentage,
            "correct_answers": item["attempt"].correct_answers,
            "wrong_answers": item["attempt"].wrong_answers,
            "total_questions": item["attempt"].total_questions,
            "submitted_at": item["attempt"].submitted_at,
            "is_eligible": is_eligible or (confirmation_status == "Confirmed"),
            "confirmation_status": confirmation_status,
            "is_excluded": item["is_excluded"],
            "excluded_reason": excluded_reason,
            
            # New fields
            "entrance_score": item["entrance_score"],
            "entrance_total_marks": item["entrance_total_marks"],
            "entrance_percentage": item["entrance_percentage"],
            "entrance_weighted_score": item["entrance_weighted_score"],
            "ug_weighted_score": item["ug_weighted_score"],
            "final_score": item["final_score"],
            "final_score_breakdown_text": breakdown_text
        }
        final_list.append(entry)

    # Default filter out excluded candidates unless explicitly requested
    if not show_excluded:
        final_list = [x for x in final_list if not x["is_excluded"]]

    # Apply search and community filters in memory
    filtered_list = []
    for item in final_list:
        if community and community != "All":
            target_comm = community.strip().upper()
            if target_comm == "BC(M)":
                target_comm = "BCM"
            elif target_comm == "MBC&DNC":
                target_comm = "MBC"
            elif target_comm == "SC(A)":
                target_comm = "SCA"
            
            if item["final_selection_bucket_code"] != target_comm:
                continue

        if search:
            search_lower = search.lower().strip()
            if search_lower not in item["student_name"].lower() and search_lower not in item["application_number"].lower():
                continue

        filtered_list.append(item)

    return filtered_list


@router.get("/course-rankings", response_model=List[CourseRankingEntry])
def get_course_rankings(
    course_code: str,
    search: Optional[str] = Query(None),
    community: Optional[str] = Query(None),
    show_excluded: bool = Query(False),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return get_course_rankings_internal(db, course_code, search, community, show_excluded)


@router.get("/export")
def export_results_excel(
    course_code: str,
    search: Optional[str] = Query(None),
    community: Optional[str] = Query(None),
    show_excluded: bool = Query(True),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    results = get_course_rankings_internal(db, course_code, search, community, show_excluded)
    
    export_data = []
    for r in results:
        deg_str = ", ".join(r["degrees"])
        
        active_rank_val = r["active_rank"] if r["active_rank"] != -1 else "Excluded"
        comm_rank_val = r["community_rank"] if r["community_rank"] != -1 else "N/A"
        
        export_data.append({
            "Course Code": course_code.upper(),
            "Original Rank": r["original_rank"],
            "Active Rank": active_rank_val,
            "Eligibility Status": "Eligible" if r["is_eligible"] else "Waitlisted",
            "Confirmation Status": r["confirmation_status"],
            "Excluded Reason": r["excluded_reason"] or "",
            "Application Number": r["application_number"],
            "Student Name": r["student_name"],
            "Degrees Applied": deg_str,
            "Raw Community": r["raw_community"],
            "Normalized Community": r["normalized_community"],
            "Open Competition Rank": r["open_competition_rank"] if r["open_competition_rank"] != -1 else "N/A",
            "Community Rank": comm_rank_val,
            "Community Seat Count": r["community_seat_count"],
            "Final Selection Bucket Code": r["final_selection_bucket_code"],
            "Final Selection Bucket Name": r["final_selection_bucket_name"],
            "Community Eligibility Status": r["community_eligibility_status"],
            "Entrance Score": r["entrance_score"],
            "Entrance Total": r["entrance_total_marks"],
            "Entrance Percentage": r["entrance_percentage"],
            "Entrance 50% Component": r["entrance_weighted_score"],
            "UG Percentage": r["ug_percentage"] if r["ug_percentage"] is not None else "Incomplete",
            "UG 50% Component": r["ug_weighted_score"] if r["ug_weighted_score"] is not None else "N/A",
            "Final Score": r["final_score"] if r["final_score"] is not None else "Incomplete",
            "Total Questions": r["total_questions"],
            "Correct Answers": r["correct_answers"],
            "Wrong Answers": r["wrong_answers"],
            "Submitted At": r["submitted_at"].strftime("%Y-%m-%d %H:%M:%S") if r["submitted_at"] else ""
        })
        
    df = pd.DataFrame(export_data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f"{course_code.upper()} Rankings")
    output.seek(0)
    
    filename = f"Rankings_{course_code.upper()}.xlsx"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        output,
        headers=headers,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@router.get("/my-results")
def get_my_results(
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    # Verify exam configuration results visibility
    exam = db.query(Exam).first()
    result_visibility = exam.result_visibility if exam else True

    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.is_submitted == True
    ).first()

    if not attempt:
        return {
            "has_results": False,
            "result_visibility": result_visibility,
            "candidate_name": current_candidate.full_name,
            "mobile_number": current_candidate.mobile_number,
            "applications": []
        }

    # For each application, compute their rank in that specific course rankings list
    apps_list = db.query(StudentApplication).filter(
        StudentApplication.candidate_id == current_candidate.id,
        StudentApplication.is_active == True
    ).all()

    my_rankings = []
    for app in apps_list:
        course_rankings = get_course_rankings_internal(db, app.course.code, show_excluded=True)
        # Find this candidate in the course rankings
        c_entry = next((x for x in course_rankings if x["candidate_id"] == current_candidate.id), None)
        
        if c_entry:
            my_rankings.append({
                "course_code": app.course.code,
                "course_name": app.course.name,
                "application_number": app.application_number,
                "original_rank": c_entry["original_rank"],
                "active_rank": c_entry["active_rank"],
                "is_eligible": c_entry["is_eligible"],
                "confirmation_status": c_entry["confirmation_status"],
                "excluded_reason": c_entry["excluded_reason"],
                
                # Breakdown details
                "entrance_score": c_entry["entrance_score"],
                "entrance_total_marks": c_entry["entrance_total_marks"],
                "entrance_percentage": c_entry["entrance_percentage"],
                "entrance_weighted_score": c_entry["entrance_weighted_score"],
                "ug_percentage": c_entry["ug_percentage"],
                "ug_weighted_score": c_entry["ug_weighted_score"],
                "final_score": c_entry["final_score"],
                "final_score_breakdown_text": c_entry["final_score_breakdown_text"]
            })

    first_app = apps_list[0] if apps_list else None
    first_rank_entry = None
    if first_app and my_rankings:
        first_rank_entry = next((r for r in my_rankings if r["course_code"] == first_app.course.code), None)

    if first_rank_entry:
        entrance_total_marks = first_rank_entry["entrance_total_marks"]
        entrance_weighted_score = first_rank_entry["entrance_weighted_score"]
        ug_percentage = first_rank_entry["ug_percentage"]
        ug_weighted_score = first_rank_entry["ug_weighted_score"]
        final_score = first_rank_entry["final_score"]
    else:
        # fallback
        entrance_total_marks = 100.0
        entrance_weighted_score = attempt.percentage * 0.5
        ug_percentage = first_app.ug_marks if first_app else None
        ug_weighted_score = ug_percentage * 0.5 if ug_percentage is not None else None
        final_score = round(entrance_weighted_score + ug_weighted_score, 2) if ug_weighted_score is not None else None

    return {
        "has_results": True,
        "result_visibility": result_visibility,
        "candidate_name": current_candidate.full_name,
        "mobile_number": current_candidate.mobile_number,
        "attempt_id": attempt.id,
        "total_questions": attempt.total_questions,
        "attempted_questions": attempt.total_questions, # completed
        "correct_answers": attempt.correct_answers,
        "wrong_answers": attempt.wrong_answers,
        "score": attempt.score,
        "percentage": attempt.percentage,
        "ug_percentage": ug_percentage,
        "entrance_percentage": attempt.percentage,
        
        # Breakdown fields for Result page
        "entrance_total_marks": entrance_total_marks,
        "entrance_weighted_score": entrance_weighted_score,
        "ug_weighted_score": ug_weighted_score,
        "final_score": final_score,
        "final_percentage": final_score if final_score is not None else 0.0,
        "rankings": my_rankings
    }
