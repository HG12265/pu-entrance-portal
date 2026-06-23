import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import ExamAttempt, StudentApplication, Candidate, Course, Admin
from app.schemas import CourseRankingEntry
from app.auth import get_current_admin, get_current_candidate

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

    # 3. Sort primarily by exam score descending, then by attempt percentage descending
    apps.sort(key=lambda x: (x[2].score, x[2].percentage), reverse=True)

    # 4. Compute original rank (standard competition ranking based on exam score)
    orig_ranked = []
    current_orig_rank = 1
    for idx, (app_rec, candidate, attempt) in enumerate(apps):
        if idx > 0 and attempt.score < apps[idx - 1][2].score:
            current_orig_rank = idx + 1
        orig_ranked.append((app_rec, candidate, attempt, current_orig_rank))

    # 5. Compute active rank (excluding candidates admitted to another course)
    final_list = []
    active_idx = 0
    
    for app_rec, candidate, attempt, orig_rank in orig_ranked:
        is_admitted_elsewhere = candidate.admitted_course_id is not None and candidate.admitted_course_id != course.id
        
        excluded_reason = None
        if is_admitted_elsewhere:
            adm_course = db.query(Course).filter(Course.id == candidate.admitted_course_id).first()
            excluded_reason = f"Admitted to {adm_course.code}" if adm_course else "Admitted to another course"

        active_rank = -1
        if not is_admitted_elsewhere:
            active_rank = 1
            # Find the last added active candidate in final_list
            last_active = next((x for x in reversed(final_list) if not x["is_excluded"]), None)
            if last_active:
                if attempt.score < last_active["score"]:
                    active_rank = active_idx + 1
                else:
                    active_rank = last_active["active_rank"]
            active_idx += 1

        degrees = [ap.course.code for ap in candidate.applications]
        is_eligible = (not is_admitted_elsewhere) and (active_rank <= course.seat_count)

        if candidate.admitted_course_id == course.id:
            confirmation_status = "Confirmed"
        elif is_admitted_elsewhere:
            confirmation_status = "Excluded"
        elif is_eligible:
            confirmation_status = "Eligible"
        else:
            confirmation_status = "Waitlisted"

        entry = {
            "rank": active_rank if not is_admitted_elsewhere else orig_rank,
            "original_rank": orig_rank,
            "active_rank": active_rank,
            "id": attempt.id,
            "candidate_id": candidate.id,
            "application_number": app_rec.application_number,
            "student_name": app_rec.full_name,
            "degrees": degrees,
            "community": app_rec.community or "OC",
            "ug_percentage": app_rec.ug_marks or 0.0,
            "score": attempt.score,
            "percentage": attempt.percentage,
            "correct_answers": attempt.correct_answers,
            "wrong_answers": attempt.wrong_answers,
            "total_questions": attempt.total_questions,
            "submitted_at": attempt.submitted_at,
            "is_eligible": is_eligible,
            "confirmation_status": confirmation_status,
            "is_excluded": is_admitted_elsewhere,
            "excluded_reason": excluded_reason
        }
        final_list.append(entry)

    # 6. Default filter out excluded candidates unless explicitly requested
    if not show_excluded:
        final_list = [x for x in final_list if not x["is_excluded"]]

    # 7. Apply search and community filters in memory
    filtered_list = []
    for item in final_list:
        if community and community != "All":
            target_comm = community.lower().strip()
            item_comm = item["community"].lower().strip()
            
            if target_comm == "oc" and not (item_comm.startswith("oc") or item_comm in ["open", "general", "ur"]):
                continue
            elif target_comm == "bc" and not (item_comm.startswith("bc") or item_comm.startswith("obc")):
                continue
            elif target_comm == "mbc" and not (item_comm.startswith("mbc") or item_comm.startswith("dnc")):
                continue
            elif target_comm == "sc" and not item_comm.startswith("sc"):
                continue
            elif target_comm == "st" and not item_comm.startswith("st"):
                continue
            elif target_comm not in ["oc", "bc", "mbc", "sc", "st"] and target_comm not in item_comm:
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
        
        # Display -1 as N/A or Blank for active_rank if excluded
        active_rank_val = r["active_rank"] if r["active_rank"] != -1 else "Excluded"
        
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
            "Community": r["community"],
            "UG %": r["ug_percentage"],
            "Total Questions": r["total_questions"],
            "Correct Answers": r["correct_answers"],
            "Wrong Answers": r["wrong_answers"],
            "Marks Obtained": r["score"],
            "Exam Percentage": r["percentage"],
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
                "excluded_reason": c_entry["excluded_reason"]
            })

    first_app = current_candidate.applications[0] if current_candidate.applications else None
    ug_perc = first_app.ug_marks or 0.0 if first_app else 0.0
    final_perc = round((ug_perc * 0.5) + (attempt.percentage * 0.5), 2)

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
        "ug_percentage": ug_perc,
        "entrance_percentage": attempt.percentage,
        "final_percentage": final_perc,
        "rankings": my_rankings
    }
