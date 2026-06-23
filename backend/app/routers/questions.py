import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Question, Exam, Admin
from app.schemas import QuestionCreate, QuestionResponse
from app.auth import get_current_admin
from app.utils.parts import normalize_question_part

router = APIRouter(prefix="/api/v1/questions", tags=["Questions"])

def get_or_create_exam(db: Session) -> Exam:
    exam = db.query(Exam).first()
    if not exam:
        import datetime
        exam = Exam(
            name="Periyar University Entrance Examination 2026",
            total_questions=100,
            duration_minutes=120,
            start_date=datetime.datetime.utcnow(),
            end_date=datetime.datetime.utcnow() + datetime.timedelta(days=30),
            result_visibility=True
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
    return exam

# Admin CRUD
@router.get("", response_model=List[QuestionResponse])
def get_all_questions(current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = get_or_create_exam(db)
    return db.query(Question).filter(Question.exam_id == exam.id).all()

@router.post("", response_model=QuestionResponse)
def create_question(question_data: QuestionCreate, current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = get_or_create_exam(db)
    p_code, p_name, p_order = None, None, None
    if question_data.part_code:
        try:
            p_code, p_name, p_order = normalize_question_part(question_data.part_code)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    new_q = Question(
        exam_id=exam.id,
        question_text=question_data.question_text,
        option_a=question_data.option_a,
        option_b=question_data.option_b,
        option_c=question_data.option_c,
        option_d=question_data.option_d,
        correct_option=question_data.correct_option.upper(),
        marks=question_data.marks,
        image_url=question_data.image_url,
        option_a_image_url=question_data.option_a_image_url,
        option_b_image_url=question_data.option_b_image_url,
        option_c_image_url=question_data.option_c_image_url,
        option_d_image_url=question_data.option_d_image_url,
        part_code=p_code,
        part_name=p_name,
        part_order=p_order,
        source_s_no=question_data.source_s_no
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return new_q

@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(question_id: int, question_data: QuestionCreate, current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    p_code, p_name, p_order = None, None, None
    if question_data.part_code:
        try:
            p_code, p_name, p_order = normalize_question_part(question_data.part_code)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    question.question_text = question_data.question_text
    question.option_a = question_data.option_a
    question.option_b = question_data.option_b
    question.option_c = question_data.option_c
    question.option_d = question_data.option_d
    question.correct_option = question_data.correct_option.upper()
    question.marks = question_data.marks
    question.image_url = question_data.image_url
    question.option_a_image_url = question_data.option_a_image_url
    question.option_b_image_url = question_data.option_b_image_url
    question.option_c_image_url = question_data.option_c_image_url
    question.option_d_image_url = question_data.option_d_image_url
    question.part_code = p_code
    question.part_name = p_name
    question.part_order = p_order
    question.source_s_no = question_data.source_s_no
    
    db.commit()
    db.refresh(question)
    return question

@router.delete("/{question_id}")
def delete_question(question_id: int, current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    db.delete(question)
    db.commit()
    return {"status": "deleted", "question_id": question_id}

def resolve_correct_option(correct: str, opt_a: str, opt_b: str, opt_c: str, opt_d: str) -> str:
    c_clean = correct.strip().upper()
    if c_clean in ["A", "B", "C", "D"]:
        return c_clean
        
    opts = {
        "A": opt_a.strip().upper(),
        "B": opt_b.strip().upper(),
        "C": opt_c.strip().upper(),
        "D": opt_d.strip().upper()
    }
    
    for key, val in opts.items():
        if c_clean == val:
            return key
            
    # Fuzzy matching by removing non-alphanumeric characters
    import re
    norm_correct = re.sub(r'[^a-z0-9]', '', c_clean.lower())
    if not norm_correct:
        return correct
        
    for key, val in opts.items():
        if norm_correct == re.sub(r'[^a-z0-9]', '', val.lower()):
            return key
            
    return correct

@router.post("/bulk-upload")
async def bulk_upload_questions(
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    import uuid
    import os
    from openpyxl import load_workbook

    # Check if the file is Excel or CSV
    if not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls") or file.filename.endswith(".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload an Excel (.xlsx/.xls) or CSV file."
        )
        
    contents = await file.read()
    exam = get_or_create_exam(db)
    
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading Excel/CSV file: {str(e)}"
        )
        
    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    # Standardize column headers to locate fields
    cols_clean = [str(c).strip().lower() for c in df.columns]

    # Mandatory Part Column check
    part_header_options = ["part", "part_code", "section", "part code", "part name", "partname"]
    part_idx = None
    for h_opt in part_header_options:
        if h_opt in cols_clean:
            part_idx = cols_clean.index(h_opt)
            break

    if part_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing mandatory 'Part' column. Rejecting upload."
        )

    # Helper to locate column positions with fallback
    def find_col_idx(header_name, default_pos, fallbacks):
        if header_name in cols_clean:
            return cols_clean.index(header_name)
        for fb in fallbacks:
            if fb in cols_clean:
                return cols_clean.index(fb)
        return default_pos

    sno_idx = find_col_idx("s. no", 0, ["s.no", "sno", "serial no", "serial number", "s. no."])
    q_idx = find_col_idx("question", 2, ["question_text", "question text", "q"])
    opt_a_idx = find_col_idx("option a", 3, ["optiona", "a"])
    opt_b_idx = find_col_idx("option b", 4, ["optionb", "b"])
    opt_c_idx = find_col_idx("option c", 5, ["optionc", "c"])
    opt_d_idx = find_col_idx("option d", 6, ["optiond", "d"])
    correct_idx = find_col_idx("correct option", 7, ["correctoption", "correct answer", "correct_option", "correct"])
    mark_idx = find_col_idx("mark", 8, ["marks"])

    # Set up static directory for images
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "question_images")
    os.makedirs(static_dir, exist_ok=True)

    # Parse drawings/images using openpyxl for Excel files
    excel_images = {}
    if not file.filename.endswith(".csv"):
        try:
            wb = load_workbook(io.BytesIO(contents))
            ws = wb.active
            if hasattr(ws, '_images'):
                for img in ws._images:
                    try:
                        r = img.anchor._from.row
                        c = img.anchor._from.col
                        fmt = getattr(img, 'format', 'png').lower()
                        img_data = img._data()
                        excel_images[(r, c)] = (img_data, fmt)
                    except Exception as inner_e:
                        print(f"[DEBUG UPLOAD] Skipping drawing: {inner_e}")
        except Exception as e:
            print(f"[DEBUG UPLOAD] Failed to load workbook with openpyxl for image parsing: {e}")

    # Helper to save image
    def save_img_file(r_idx, c_idx):
        img_tuple = excel_images.get((r_idx, c_idx))
        if not img_tuple:
            return None
        raw_data, extension = img_tuple
        file_name = f"{uuid.uuid4().hex}.{extension}"
        file_path = os.path.join(static_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(raw_data)
        return f"/api/v1/static/question_images/{file_name}"

    questions_to_create = []
    part_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    errors = []
    
    for idx, row in df.iterrows():
        excel_row = idx + 1 # 0-indexed row in df is row 1 in openpyxl (row index 0 is header)
        try:
            # Clean values helper
            def clean_val(val):
                if pd.isna(val) or val is None:
                    return ""
                v_str = str(val).strip()
                if v_str.lower() in ["nan", "none"]:
                    return ""
                return v_str

            q_text = clean_val(row.iloc[q_idx])
            part_val = clean_val(row.iloc[part_idx])
            opt_a = clean_val(row.iloc[opt_a_idx])
            opt_b = clean_val(row.iloc[opt_b_idx])
            opt_c = clean_val(row.iloc[opt_c_idx])
            opt_d = clean_val(row.iloc[opt_d_idx])
            correct = clean_val(row.iloc[correct_idx])

            # Read S. No
            try:
                s_no_val = int(float(row.iloc[sno_idx])) if not pd.isna(row.iloc[sno_idx]) else None
            except:
                s_no_val = None

            # Read Marks
            try:
                marks = float(row.iloc[mark_idx]) if not pd.isna(row.iloc[mark_idx]) else 1.0
            except:
                marks = 1.0

            # Save any embedded images for this row
            q_img = save_img_file(excel_row, q_idx)
            a_img = save_img_file(excel_row, opt_a_idx)
            b_img = save_img_file(excel_row, opt_b_idx)
            c_img = save_img_file(excel_row, opt_c_idx)
            d_img = save_img_file(excel_row, opt_d_idx)

            # Skip empty rows (no question text and no image)
            if not q_text and not q_img:
                continue

            # Part column validation
            if not part_val:
                errors.append(f"Row {excel_row + 1}: Missing part value.")
                continue

            try:
                p_code, p_name, p_order = normalize_question_part(part_val)
            except ValueError as ve:
                errors.append(f"Row {excel_row + 1}: {str(ve)}")
                continue

            # Resolve correct option
            resolved_correct = resolve_correct_option(correct, opt_a, opt_b, opt_c, opt_d)
            if resolved_correct not in ["A", "B", "C", "D"]:
                errors.append(f"Row {excel_row + 1}: Correct Answer '{correct}' must match one of the options (A, B, C, or D).")
                continue

            # Create Question object
            db_q = Question(
                exam_id=exam.id,
                question_text=q_text,
                option_a=opt_a,
                option_b=opt_b,
                option_c=opt_c,
                option_d=opt_d,
                correct_option=resolved_correct,
                marks=marks,
                image_url=q_img,
                option_a_image_url=a_img,
                option_b_image_url=b_img,
                option_c_image_url=c_img,
                option_d_image_url=d_img,
                part_code=p_code,
                part_name=p_name,
                part_order=p_order,
                source_s_no=s_no_val
            )
            questions_to_create.append(db_q)
            part_counts[p_code] += 1
            
        except Exception as row_error:
            errors.append(f"Row {excel_row + 1}: Failed to process due to: {str(row_error)}")

    # Check for formatting/parsing errors
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Upload failed due to errors in Excel rows.", "errors": errors}
        )

    # Validate exactly 25 questions per part
    mismatches = []
    expected_parts = {
        "A": ("Quantitative Ability", 25),
        "B": ("Analytical Reasoning", 25),
        "C": ("Logical Reasoning", 25),
        "D": ("Computer Awareness", 25)
    }
    for p_code, (p_name, expected_count) in expected_parts.items():
        actual = part_counts[p_code]
        if actual != expected_count:
            mismatches.append(f"Part {p_code} ({p_name}): expected {expected_count}, got {actual}")

    if mismatches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Question count validation failed. The exam must contain exactly 25 questions per part.",
                "errors": mismatches,
                "counts": part_counts
            }
        )

    # All checks passed: Delete existing questions for this exam
    db.query(Question).filter(Question.exam_id == exam.id).delete()
    db.commit()

    # Bulk insert
    for q in questions_to_create:
        db.add(q)
    db.commit()

    return {
        "status": "success",
        "added_count": len(questions_to_create),
        "part_counts": part_counts
    }

@router.post("/upload-image")
def upload_question_image(
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    import uuid
    import os
    
    # Verify file extension (must be an image)
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "png"
    if ext not in ["jpg", "jpeg", "png", "gif", "webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Allowed: JPG, JPEG, PNG, GIF, WEBP"
        )
        
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "question_images")
    os.makedirs(static_dir, exist_ok=True)
    
    file_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(static_dir, file_name)
    
    try:
        contents = file.file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save image file: {str(e)}"
        )
        
    return {"url": f"/api/v1/static/question_images/{file_name}"}
