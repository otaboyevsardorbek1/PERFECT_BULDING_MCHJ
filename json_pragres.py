import ijson
from datetime import datetime
from multiprocessing import Pool, cpu_count
import pytz


# --- 1. Vaqtni formatlovchi funksiya (har bir worker uchun) ---
def convert_time(value):
    """
    ISO vaqtni UTC+8 dan olib, Asia/Tashkent (UTC+5) ga o‘tkazadi
    va uni HH:MM-DD.MM.YYYY formatiga chiqaradi.
    """
    try:
        # ISO formatdagi vaqtni o‘qish
        dt = datetime.fromisoformat(value)

        # O‘zbekiston vaqtiga chiqarish
        uz_tz = pytz.timezone("Asia/Tashkent")
        dt_uz = dt.astimezone(uz_tz)

        # Formatlash
        return dt_uz.strftime("%H:%M-%d.%m.%Y")
    except Exception as e:
        return f"ERROR: {e} → VALUE: {value}"


# --- 2. ijson orqali JSONdan vaqtlarni streaming chiqarish ---
def extract_times(json_file):
    """
    JSONni xotiraga yuklamasdan, streaming tarzda o‘qib,
    created_at, updated_at, deleted_at vaqtlarini chiqaradi.
    """
    with open(json_file, "r", encoding="utf-8") as f:
        for prefix, event, value in ijson.parse(f):
            if (
                event == "string" and (
                    prefix.endswith("created_at") or
                    prefix.endswith("updated_at") or
                    prefix.endswith("deleted_at")
                )
            ):
                yield value  # generator, RAMni tejaydi


# --- 3. Multiprocessing orqali juda tez qayta ishlash ---
def process_large_json(json_file):

    print("[INFO] JSON ichidagi vaqtlar yig‘ilmoqda...")

    # Vaqtlar ro‘yxatini olamiz
    times = list(extract_times(json_file))

    print(f"[INFO] Jami {len(times)} ta vaqt topildi.")
    workers = cpu_count()

    print(f"[INFO] {workers} ta CPU yadro orqali yordamchi jarayonlar ishga tushdi...")

    # Multiprocessing Pool
    with Pool(workers) as pool:
        results = pool.map(convert_time, times, chunksize=500)

    print("[INFO] Vaqtlar formatlandi!")
    return results


# --- 4. Ishga tushirish ---
if __name__ == "__main__":
    file_path = "output.json"  # JSON fayling manzili

    print("[SYSTEM] Dastur ishga tushirildi...")

    formatted_times = process_large_json(file_path)

    print("\n--- FORMATLANGAN VAQTLARDAN 20 TASINI KO‘RSATAMIZ ---")
    for t in formatted_times[:20]:
        print(t)

    print("\n[OK] BARCHA VAQTLAR MUKAMMAL FORMATDA TAYYOR!")
