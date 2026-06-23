import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Question, Exam, Admin
from app.schemas import QuestionCreate, QuestionResponse
from app.auth import get_current_admin

router = APIRouter(prefix="/api/v1/questions", tags=["Questions"])

def get_or_create_exam(db: Session) -> Exam:
    exam = db.query(Exam).first()
    if not exam:
        import datetime
        exam = Exam(
            name="Periyar University Entrance Examination 2026",
            total_questions=30,
            duration_minutes=30,
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

    # Check if the file is Excel
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

    # Set up static directory for images
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "question_images")
    os.makedirs(static_dir, exist_ok=True)

    # Parse drawings/images using openpyxl for Excel files
    excel_images = {}
    print(f"[DEBUG UPLOAD] Uploaded filename: {file.filename} (Size: {len(contents)} bytes)")
    if not file.filename.endswith(".csv"):
        try:
            wb = load_workbook(io.BytesIO(contents))
            ws = wb.active
            images_found = len(getattr(ws, '_images', []))
            print(f"[DEBUG UPLOAD] Openpyxl loaded sheet '{ws.title}' and found {images_found} images.")
            if hasattr(ws, '_images'):
                for img in ws._images:
                    try:
                        r = img.anchor._from.row
                        c = img.anchor._from.col
                        fmt = getattr(img, 'format', 'png').lower()
                        img_data = img._data()
                        excel_images[(r, c)] = (img_data, fmt)
                        print(f"[DEBUG UPLOAD] Image mapped to cell ({r}, {c})")
                    except Exception as inner_e:
                        print(f"[DEBUG UPLOAD] Skipping drawing: {inner_e}")
        except Exception as e:
            print(f"[DEBUG UPLOAD] Failed to load workbook with openpyxl for image parsing: {e}")

    added_count = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            excel_row = idx + 1 # 0-indexed row in df is row 1 (first data row) in openpyxl/Excel
            
            # Clean values helper
            def clean_val(val):
                if pd.isna(val) or val is None:
                    return ""
                v_str = str(val).strip()
                if v_str.lower() in ["nan", "none"]:
                    return ""
                return v_str

            q_text = clean_val(row.iloc[0])
            opt_a = clean_val(row.iloc[1])
            opt_b = clean_val(row.iloc[2])
            opt_c = clean_val(row.iloc[3])
            opt_d = clean_val(row.iloc[4])
            correct = clean_val(row.iloc[5])
            
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

            # Save any embedded images for this row
            q_img = save_img_file(excel_row, 0)
            a_img = save_img_file(excel_row, 1)
            b_img = save_img_file(excel_row, 2)
            c_img = save_img_file(excel_row, 3)
            d_img = save_img_file(excel_row, 4)

            # Skip empty rows
            # A row is empty if q_text is empty AND there is no question image
            if not q_text and not q_img:
                continue

            # Marks defaults to 1.0 if not provided or invalid
            try:
                marks = float(row.iloc[6]) if len(row) > 6 and not pd.isna(row.iloc[6]) else 1.0
            except:
                marks = 1.0

            # Resolve the correct option
            print(f"[DEBUG UPLOAD] Row {idx + 2}: correct='{correct}' | A='{opt_a}' | B='{opt_b}' | C='{opt_c}' | D='{opt_d}'")
            resolved_correct = resolve_correct_option(correct, opt_a, opt_b, opt_c, opt_d)
            print(f"[DEBUG UPLOAD] Row {idx + 2} resolved: '{resolved_correct}'")
            if resolved_correct not in ["A", "B", "C", "D"]:
                errors.append(f"Row {idx + 2}: Correct Answer '{correct}' must be A, B, C, or D.")
                continue

            # Create question
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
                option_d_image_url=d_img
            )
            db.add(db_q)
            added_count += 1
            
        except Exception as row_error:
            errors.append(f"Row {idx + 2}: Failed to process due to: {str(row_error)}")
            
    if added_count > 0:
        db.commit()
        
    return {
        "status": "success" if not errors else "partial_success",
        "added_count": added_count,
        "errors": errors
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

