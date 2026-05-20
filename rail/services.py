import re
from datetime import datetime

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from django.utils import timezone

from .models import MovementHistory, Notification, OCRResult, OperationLog, TrackSection, Train, Wagon

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def log_action(user, action, obj=None, description=''):
    return OperationLog.objects.create(user=user if getattr(user, 'is_authenticated', False) else None, action=action, object_type=obj.__class__.__name__ if obj else '', object_id=getattr(obj, 'id', None), description=description)


def notify(user, title, message, type='info'):
    if user and user.is_authenticated:
        Notification.objects.create(user=user, title=title, message=message, type=type)


def refresh_section_occupancy():
    occupied = set(Train.objects.exclude(status=Train.DEPARTED).filter(current_section__isnull=False).values_list('current_section_id', flat=True))
    occupied.update(Wagon.objects.exclude(status='departed').filter(current_section__isnull=False).values_list('current_section_id', flat=True))
    for section in TrackSection.objects.all():
        new_value = section.id in occupied
        if section.is_occupied != new_value:
            section.is_occupied = new_value
            section.save(update_fields=['is_occupied'])


def move_object(*, user, target, section, comment=''):
    if section.is_occupied:
        raise ValueError('Выбранный участок уже занят')
    if isinstance(target, Train):
        history = MovementHistory.objects.create(object_type='train', train=target, from_track=target.current_track, from_section=target.current_section, to_track=section.track, to_section=section, moved_by=user, comment=comment)
        target.current_track = section.track
        target.current_section = section
        if target.status == Train.ARRIVED:
            target.status = Train.PLACED
        target.save()
        target.wagons.update(current_track=section.track, current_section=section)
    else:
        history = MovementHistory.objects.create(object_type='wagon', wagon=target, train=target.train, from_track=target.current_track, from_section=target.current_section, to_track=section.track, to_section=section, moved_by=user, comment=comment)
        target.current_track = section.track
        target.current_section = section
        target.save()
    refresh_section_occupancy()
    log_action(user, f'Перемещение {history.get_object_type_display().lower()}', target, comment)
    return history


def run_ocr(document):
    document.ocr_status = 'processing'
    document.save(update_fields=['ocr_status'])
    image = Image.open(document.file.path)
    image = ImageOps.grayscale(image).filter(ImageFilter.SHARPEN)
    text = pytesseract.image_to_string(image, lang='rus+eng')
    parsed = parse_ocr_text(text)
    result, _ = OCRResult.objects.update_or_create(document=document, defaults={**parsed, 'raw_text': text, 'confidence': 75 if text.strip() else 20})
    document.recognized_text = text
    document.ocr_status = 'recognized' if text.strip() else 'error'
    document.save(update_fields=['recognized_text', 'ocr_status'])
    return result


def parse_ocr_text(text):
    train_match = re.search(r'(?:состав|поезд|train)\D*(\d{3,})', text, re.I)
    wagon_match = re.search(r'(?:вагонов|wagons?)\D*(\d+)', text, re.I)
    cargo_match = re.search(r'(?:груз|cargo)\s*[:\-]?\s*([^\n\r]+)', text, re.I)
    date_match = re.search(r'(\d{2}[./-]\d{2}[./-]\d{4})', text)
    arrival_date = None
    if date_match:
        for fmt in ('%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y'):
            try:
                arrival_date = datetime.strptime(date_match.group(1), fmt).date()
                break
            except ValueError:
                pass
    return {'train_number': train_match.group(1) if train_match else '', 'wagon_count': int(wagon_match.group(1)) if wagon_match else None, 'cargo_type': cargo_match.group(1).strip()[:120] if cargo_match else '', 'arrival_date': arrival_date}


def confirm_ocr(result, user):
    result.confirmed_by = user
    result.confirmed_at = timezone.now()
    result.save()
    result.document.ocr_status = 'confirmed'
    result.document.save(update_fields=['ocr_status'])
    log_action(user, 'Подтверждение OCR', result.document, f'Подтвержден OCR документа {result.document_id}')
