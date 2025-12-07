#!/usr/bin/env python3
import requests
import json
from urllib.parse import urlparse

def extract_owner_repo(github_url):
    """
    GitHub URL-dan owner va repo nomini ajratadi
    """
    parsed = urlparse(github_url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        raise ValueError("Notog'ri GitHub URL")
    owner, repo = path_parts[0], path_parts[1]
    return owner, repo

def get_repo_files(owner, repo, branch="main"):
    """
    GitHub API orqali berilgan repo va branchdagi barcha fayllar URLini oladi
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(api_url)
    
    # Branch xatolik bo'lsa, master ni tekshirish
    if response.status_code == 404 and branch == "main":
        branch = "master"
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(f"API xatosi: {response.status_code} - {response.text}")
    
    data = response.json()
    files = []
    files.append(f"REPO_URL:https://github.com/{owner}/{repo}")
    for item in data.get("tree", []):
        if item["type"] == "blob":  # faqat fayllar
            file_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{item['path']}"
            files.append(file_url)
    return files

if __name__ == "__main__":
    github_url = input("GitHub repo URL: ").strip()
    
    try:
        owner, repo = extract_owner_repo(github_url)
        files_list = get_repo_files(owner, repo)
        
        # JSON faylga saqlash
        json_filename = f"{owner}_{repo}_files.json"
        with open(json_filename, "w") as f:
            json.dump(files_list, f, indent=4)
        
        print(f"\nNatija {json_filename} faylga saqlandi.")
        # print(json.dumps(files_list, indent=4))
    except Exception as e:
        print("Xato yuz berdi:", e)
