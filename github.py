# #!/usr/bin/env python3
# import requests
# import json
# import re
# from urllib.parse import urlparse, urlunparse
# from typing import List, Dict, Optional

# class GitHubRawURLGenerator:
#     """
#     GitHub repodagi barcha fayllarning RAW URL'larini olish
#     """
    
#     def __init__(self):
#         self.session = requests.Session()
#         self.session.headers.update({
#             "User-Agent": "GitHub-Raw-URL-Fetcher/1.0",
#             "Accept": "application/vnd.github.v3+json"
#         })
    
#     def get_default_branch(self, owner: str, repo: str) -> str:
#         """
#         Reponing default branchini aniqlash
#         """
#         api_url = f"https://api.github.com/repos/{owner}/{repo}"
#         try:
#             response = self.session.get(api_url, timeout=10)
#             if response.status_code == 200:
#                 data = response.json()
#                 return data.get("default_branch", "main")
#         except:
#             pass
#         return "main"
    
#     def extract_owner_repo(self, github_url: str) -> tuple:
#         """
#         GitHub URL-dan owner va repo nomini ajratadi
#         """
#         # .git ni olib tashlash
#         github_url = github_url.replace('.git', '')
        
#         parsed = urlparse(github_url)
#         path_parts = parsed.path.strip("/").split("/")
        
#         if len(path_parts) < 2:
#             raise ValueError(f"Noto'g'ri GitHub URL: {github_url}")
        
#         owner, repo = path_parts[0], path_parts[1]
        
#         return owner, repo
    
#     def convert_to_raw_url(self, github_url: str) -> Optional[str]:
#         """
#         Oddiy GitHub URL'ini raw URL'iga o'zgartiradi
#         github.com/owner/repo/blob/branch/path/file.ext -> raw.githubusercontent.com/owner/repo/branch/path/file.ext
#         """
#         patterns = [
#             r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)',
#             r'https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)'
#         ]
        
#         for pattern in patterns:
#             match = re.match(pattern, github_url)
#             if match:
#                 owner, repo, branch, file_path = match.groups()
#                 # Agar file_path papka bo'lsa (tree uchun), uni o'tkazib yuborish
#                 if '.' not in file_path.split('/')[-1] and '/' not in file_path:
#                     continue
#                 return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        
#         return None
    
#     def get_repo_raw_urls(self, github_url: str, include_folders: bool = False) -> Dict:
#         """
#         Repodagi barcha fayllarning RAW URL'larini olish
        
#         Args:
#             github_url: GitHub repo URL
#             include_folders: Papkalarni ham qo'shish
            
#         Returns:
#             Dict: Natijalar
#         """
#         try:
#             owner, repo = self.extract_owner_repo(github_url)
#             branch = self.get_default_branch(owner, repo)
            
#             print(f"🔍 Repo: {owner}/{repo}")
#             print(f"🌿 Branch: {branch}")
            
#             # API orqali fayllar ro'yxatini olish
#             api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
#             response = self.session.get(api_url, timeout=30)
            
#             if response.status_code != 200:
#                 # Branch xatolik bo'lsa, master ni tekshirish
#                 if response.status_code == 404 and branch == "main":
#                     branch = "master"
#                     api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
#                     response = self.session.get(api_url, timeout=30)
                
#                 if response.status_code != 200:
#                     raise Exception(f"API xatosi: {response.status_code} - {response.text}")
            
#             data = response.json()
            
#             results = {
#                 "metadata": {
#                     "owner": owner,
#                     "repo": repo,
#                     "branch": branch,
#                     "repo_url": f"https://github.com/{owner}/{repo}",
#                     "total_files": 0,
#                     "total_raw_urls": 0
#                 },
#                 "raw_urls": [],
#                 "file_details": []
#             }
            
#             file_count = 0
#             for item in data.get("tree", []):
#                 if item["type"] == "blob":  # faqat fayllar
#                     file_path = item["path"]
#                     raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
                    
#                     results["raw_urls"].append(raw_url)
                    
#                     # Fayl tafsilotlari
#                     file_info = {
#                         "path": file_path,
#                         "filename": file_path.split('/')[-1],
#                         "raw_url": raw_url,
#                         "github_url": f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}",
#                         "size": item.get("size", 0),
#                         "sha": item.get("sha", ""),
#                         "mode": item.get("mode", "")
#                     }
#                     results["file_details"].append(file_info)
                    
#                     file_count += 1
            
#             results["metadata"]["total_files"] = file_count
#             results["metadata"]["total_raw_urls"] = len(results["raw_urls"])
            
#             return results
            
#         except Exception as e:
#             raise Exception(f"Repo yuklashda xato: {str(e)}")
    
#     def save_to_json(self, results: Dict, filename: Optional[str] = None) -> str:
#         """
#         Natijalarni JSON faylga saqlash
#         """
#         if filename is None:
#             owner = results["metadata"]["owner"]
#             repo = results["metadata"]["repo"]
#             filename = f"{owner}_{repo}_raw_urls.json"
        
#         with open(filename, "w", encoding="utf-8") as f:
#             json.dump(results, f, indent=4, ensure_ascii=False)
        
#         return filename
    
#     def save_urls_to_text(self, results: Dict, filename: Optional[str] = None) -> str:
#         """
#         Faqat RAW URL'larini text faylga saqlash
#         """
#         if filename is None:
#             owner = results["metadata"]["owner"]
#             repo = results["metadata"]["repo"]
#             filename = f"{owner}_{repo}_raw_urls.txt"
        
#         with open(filename, "w", encoding="utf-8") as f:
#             f.write(f"# {results['metadata']['repo_url']}\n")
#             f.write(f"# Branch: {results['metadata']['branch']}\n")
#             f.write(f"# Total files: {results['metadata']['total_files']}\n")
#             f.write("=" * 50 + "\n\n")
            
#             for url in results["raw_urls"]:
#                 f.write(url + "\n")
        
#         return filename

# def main():
#     """
#     Asosiy dastur
#     """
#     print("=" * 60)
#     print("GitHub RAW URL Generator v1.0")
#     print("github.com -> raw.githubusercontent.com")
#     print("=" * 60)
    
#     generator = GitHubRawURLGenerator()
    
#     # URL kiritish
#     default_url = "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ"
#     github_url = input(f"GitHub repo URL (Enter for {default_url}): ").strip()
    
#     if not github_url:
#         github_url = default_url
    
#     try:
#         print(f"\n⏳ {github_url} tahlil qilinmoqda...")
        
#         # RAW URL'larni olish
#         results = generator.get_repo_raw_urls(github_url)
        
#         print(f"✅ {results['metadata']['total_files']} ta fayl topildi")
        
#         # Natijalarni ko'rsatish
#         print(f"\n📋 RAW URL'lar (dastlabki 10 tasi):")
#         for i, url in enumerate(results["raw_urls"][:10], 1):
#             print(f"{i:2}. {url}")
        
#         if len(results["raw_urls"]) > 10:
#             print(f"... va yana {len(results['raw_urls']) - 10} ta")
        
#         # Fayllarni guruhlash
#         print(f"\n📁 Fayl kengaytmalari bo'yicha:")
#         extensions = {}
#         for file_info in results["file_details"]:
#             ext = file_info["filename"].split('.')[-1] if '.' in file_info["filename"] else "no-ext"
#             extensions[ext] = extensions.get(ext, 0) + 1
        
#         for ext, count in sorted(extensions.items()):
#             print(f"  .{ext}: {count} ta")
        
#         # Saqlash
#         print("\n💾 Saqlash variantlari:")
#         print("1. JSON fayl (to'liq ma'lumot)")
#         print("2. Text fayl (faqat URL'lar)")
#         print("3. Ikkala fayl ham")
        
#         choice = input("Tanlang (1-3, default=3): ").strip() or "3"
        
#         if choice in ["1", "3"]:
#             json_file = generator.save_to_json(results)
#             print(f"  ✅ JSON saqlandi: {json_file}")
        
#         if choice in ["2", "3"]:
#             txt_file = generator.save_urls_to_text(results)
#             print(f"  ✅ Text saqlandi: {txt_file}")
        
#         # URL'lar ro'yxatini test qilish (ixtiyoriy)
#         test_download = input("\n📥 Dastlabki 3 ta faylni test yuklab ko'rish? (y/N): ").strip().lower()
#         if test_download in ['y', 'yes', 'ha']:
#             print("\n🧪 Test yuklash:")
#             for i, url in enumerate(results["raw_urls"][:3], 1):
#                 print(f"\n{i}. {url}")
#                 try:
#                     response = requests.get(url, timeout=10)
#                     if response.status_code == 200:
#                         content_preview = response.text[:100].replace('\n', ' ')
#                         print(f"   ✅ OK - {len(response.text)} belgi")
#                         print(f"   📄 Preview: {content_preview}...")
#                     else:
#                         print(f"   ❌ Xato: {response.status_code}")
#                 except Exception as e:
#                     print(f"   ❌ Yuklash xatosi: {e}")
        
#         print(f"\n✨ Tugatildi! Jami {results['metadata']['total_files']} ta fayl uchun RAW URL'lar yaratildi.")
        
#     except Exception as e:
#         print(f"\n❌ Xato yuz berdi: {str(e)}")

# if __name__ == "__main__":
#     main()


###########################################################################################################################################
#!/usr/bin/env python3
import json
import re
from typing import List

def convert_to_raw_url(blob_url: str) -> str:
    """
    GitHub blob URL'ini raw URL'iga o'zgartiradi
    
    github.com/owner/repo/blob/branch/path/file.ext 
    -> 
    raw.githubusercontent.com/owner/repo/branch/path/file.ext
    """
    # Pattern: github.com/owner/repo/blob/branch/path
    pattern = r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)'
    match = re.match(pattern, blob_url)
    
    if match:
        owner, repo, branch, file_path = match.groups()
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        return raw_url
    
    # Agar allaqachon raw URL bo'lsa, o'zgarishsiz qaytarish
    if "raw.githubusercontent.com" in blob_url:
        return blob_url
    
    # Agar o'zgartirib bo'lmasa, asl URL ni qaytarish
    return blob_url

def process_json_file(input_file: str, output_file: str = None):
    """
    JSON fayldagi GitHub URL'larini raw formatga o'zgartiradi
    """
    # JSON faylni o'qish
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Agar data ro'yxat bo'lsa
    if isinstance(data, list):
        converted_urls = []
        
        for item in data:
            # Agar REPO_URL bo'lsa (sizning formatda "REPO_URL:https://...")
            if isinstance(item, str):
                if item.startswith("REPO_URL:"):
                    # REPO_URL ni saqlash
                    converted_urls.append(item)
                else:
                    # Oddiy URL ni o'zgartirish
                    raw_url = convert_to_raw_url(item)
                    converted_urls.append(raw_url)
            else:
                # Agar string bo'lmasa, o'zgarishsiz qoldirish
                converted_urls.append(item)
        
        result = converted_urls
    
    elif isinstance(data, dict) and "raw_urls" in data:
        # Agar dict va ichida raw_urls bo'lsa
        converted_urls = []
        for url in data["raw_urls"]:
            raw_url = convert_to_raw_url(url)
            converted_urls.append(raw_url)
        
        data["raw_urls"] = converted_urls
        result = data
    
    else:
        print("❌ Noto'g'ri JSON format")
        return
    
    # Output fayl nomi
    if output_file is None:
        output_file = input_file.replace('.json', '_raw.json')
    
    # Saqlash
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"✅ {len(converted_urls) if isinstance(data, list) else len(data.get('raw_urls', []))} ta URL o'zgartirildi")
    print(f"💾 Natijalar saqlandi: {output_file}")
    
    # Birinchi 5 ta URL ni ko'rsatish
    print(f"\n📋 Namuna URL'lar:")
    urls_to_show = converted_urls if isinstance(data, list) else data.get('raw_urls', [])
    
    # REPO_URL'ni o'tkazib yuborish
    show_urls = []
    for url in urls_to_show[:6]:  # Birinchi 6 tasi
        if isinstance(url, str) and url.startswith("REPO_URL:"):
            continue
        show_urls.append(url)
    
    for i, url in enumerate(show_urls[:5], 1):
        print(f"{i}. {url}")
    
    return result

def convert_url_list(url_list: List[str]) -> List[str]:
    """
    URL'lar ro'yxatini to'g'ridan-to'g'ri o'zgartiradi
    """
    raw_urls = []
    
    for blob_url in url_list:
        raw_url = convert_to_raw_url(blob_url)
        raw_urls.append(raw_url)
    
    return raw_urls

def main():
    """
    Asosiy dastur - sizning bergan URL'lar ro'yxatini o'zgartiradi
    """
    # Sizning bergan URL'lar ro'yxati
    blob_urls = [
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot.txt",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/.env.example",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/README.md",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/alembic.ini",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/config.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/data/database.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/database/__init__.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/database/crud.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/database/db.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/database/models.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/database/session.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/__init__.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/admin.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/employees.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/notifications.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/production.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/reports.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/sales.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/start.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/handlers/warehouse.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/keyboards/__init__.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/keyboards/admin_menu.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/keyboards/inline_keyboards.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/keyboards/main_menu.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/main.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/requirements.txt",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/__init__.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/calculations.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/charts.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/excel_reports.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/formulas.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/helpers.py",
        "https://github.com/otaboyevsardorbek1/PERFECT_BULDING_MCHJ/blob/master/construction_factory_bot/utils/notifications.py"
    ]
    
    print("🔗 GitHub blob URL'larini raw formatga o'zgartiramiz...")
    print(f"📊 Jami {len(blob_urls)} ta URL")
    
    # URL'lar ro'yxatini o'zgartiramiz
    raw_urls = convert_url_list(blob_urls)
    
    # JSON faylga saqlash
    output_data = {
        "metadata": {
            "repo": "otaboyevsardorbek1/PERFECT_BULDING_MCHJ",
            "branch": "master",
            "total_files": len(raw_urls),
            "original_format": "blob",
            "converted_format": "raw"
        },
        "raw_urls": raw_urls
    }
    
    # Saqlash
    output_file = "PERFECT_BULDING_MCHJ_raw_urls.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ {len(raw_urls)} ta URL o'zgartirildi")
    print(f"💾 Natijalar saqlandi: {output_file}")
    
    # Birinchi 5 ta URL ni ko'rsatish
    print(f"\n📋 Namuna URL'lar:")
    for i, url in enumerate(raw_urls[:5], 1):
        print(f"{i}. {url}")
    
    if len(raw_urls) > 5:
        print(f"... va yana {len(raw_urls) - 5} ta")
    
    # Text faylga ham saqlash (faqat URL'lar)
    txt_file = "PERFECT_BULDING_MCHJ_raw_urls.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("# GitHub RAW URLs\n")
        f.write("# Repo: otaboyevsardorbek1/PERFECT_BULDING_MCHJ\n")
        f.write("# Branch: master\n")
        f.write(f"# Total files: {len(raw_urls)}\n")
        f.write("=" * 50 + "\n\n")
        
        for url in raw_urls:
            f.write(url + "\n")
    
    print(f"📄 Text fayl ham saqlandi: {txt_file}")
    
    return output_data

if __name__ == "__main__":
    # JSON fayl nomi (agar JSON fayldan o'qish kerak bo'lsa)
    json_file = None  # "otaboyevsardorbek1_PERFECT_BULDING_MCHJ_files.json"
    
    if json_file:
        # JSON fayldan o'qib o'zgartiramiz
        process_json_file(json_file)
    else:
        # To'g'ridan-to'g'ri URL ro'yxatini o'zgartiramiz
        main()