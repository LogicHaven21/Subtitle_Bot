import os
import pyperclip

def clean_clipboard():
    """
    حافظه کلیپ‌بورد ویندوز را کاملاً خالی می‌کند.
    
    چرا این تابع مهم است؟
    در bot_engine، ما مدام چک می‌کنیم که آیا متن جدیدی وارد کلیپ‌بورد شده یا نه.
    اگر کلیپ‌بورد از قبل پر باشد، ربات ممکن است متن قدیمی را به جای ترجمه جدید بردارد.
    این تابع قبل از زدن دکمه Copy در مرورگر اجرا می‌شود تا این باگ را رفع کند.
    """
    try:
        pyperclip.copy("")  # قرار دادن رشته خالی در کلیپ‌بورد
    except Exception as e:
        print(f"Warning: Clipboard clear failed: {e}")

def read_subtitle(file_path):
    """
    محتوای فایل زیرنویس (SRT) را می‌خواند.
    
    ویژگی:
    سعی می‌کند با فرمت UTF-8 بخواند که استاندارد است.
    اگر فایل قدیمی بود و خطا داد، ارور را مدیریت می‌کند تا برنامه کرش نکند.
    """
    if not os.path.exists(file_path):
        return None

    try:
        # اکثر فایل‌های SRT استاندارد UTF-8 هستند
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            # تلاش دوم: گاهی زیرنویس‌ها UTF-8-SIG هستند (هدر دارند)
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception:
            return None
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None


def compute_output_path(original_path, output_root_folder, input_root_folder):
    """مسیر خروجی معادل را با پسوند _FA می‌سازد."""
    original_path = os.path.normpath(original_path)
    input_root_folder = os.path.normpath(input_root_folder)
    output_root_folder = os.path.normpath(output_root_folder)

    if input_root_folder in original_path:
        relative_path = os.path.relpath(original_path, input_root_folder)
    else:
        relative_path = os.path.basename(original_path)

    full_output_path = os.path.join(output_root_folder, relative_path)
    folder_path = os.path.dirname(full_output_path)
    filename = os.path.basename(full_output_path)
    name_part, extension = os.path.splitext(filename)
    new_filename = f"{name_part}_FA{extension}"
    final_file_path = os.path.join(folder_path, new_filename)
    return final_file_path


def is_already_translated(original_path, output_root_folder, input_root_folder, min_bytes=50):
    """بررسی می‌کند فایل ترجمه‌شده (_FA) وجود دارد و خالی نیست."""
    target = compute_output_path(original_path, output_root_folder, input_root_folder)
    return os.path.exists(target) and os.path.getsize(target) >= min_bytes

def smart_save_file(original_path, content, output_root_folder, input_root_folder):
    """
    فایل ترجمه شده را با حفظ ساختار پوشه‌ها و نام‌گذاری صحیح ذخیره می‌کند.
    
    Args:
        original_path: مسیر کامل فایل اصلی (انگلیسی)
        content: متن ترجمه شده که باید ذخیره شود
        output_root_folder: پوشه‌ای که کاربر برای خروجی انتخاب کرده
        input_root_folder: پوشه‌ای که کاربر برای ورودی انتخاب کرده
        
    Returns:
        tuple: (مسیر نهایی فایل ذخیره شده, وضعیت موفقیت True/False)
    """
    try:
        final_file_path = compute_output_path(original_path, output_root_folder, input_root_folder)
        folder_path = os.path.dirname(final_file_path)
        
        # 5. ساخت پوشه‌ها (Directory Creation)
        # اگر پوشه Season 1 در مقصد وجود نداشت، آن را می‌سازد
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            
        # 6. ذخیره نهایی (Saving)
        # حتماً با encoding="utf-8" ذخیره می‌کنیم تا فارسی درست نمایش داده شود
        with open(final_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return final_file_path, True

    except Exception as e:
        # برگرداندن خطا برای نمایش در لاگ‌های ربات
        return f"Error: {str(e)}", False