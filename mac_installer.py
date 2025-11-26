import os
import shutil
import sys
import subprocess
import requests
import platform
import zipfile
import re
from pathlib import Path

# --- CONFIGURATION ---
GITHUB_REPO = "KZO999/mods"
GITHUB_FOLDER = ""

# NeoForge Config
NEOFORGE_VERSION = "21.1.215"
NEOFORGE_URL = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{NEOFORGE_VERSION}/neoforge-{NEOFORGE_VERSION}-installer.jar"

# Java 21 Links (Adoptium)
JAVA_ARM64_URL = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_aarch64_mac_hotspot_21.0.5_11.pkg"
JAVA_X64_URL = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_x64_mac_hotspot_21.0.5_11.pkg"

# Paths (Mac Specific)
USER_HOME = Path.home()
MINECRAFT_DIR = USER_HOME / "Library" / "Application Support" / "minecraft"
MODS_DIR = MINECRAFT_DIR / "mods"
TEMP_DIR = Path("/tmp/mod_installer")

def download_file(url, dest_folder, filename=None):
    if not dest_folder.exists():
        dest_folder.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = url.split('/')[-1]
    
    dest_path = dest_folder / filename
    print(f"Downloading: {filename}...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        with requests.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return dest_path
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None

def check_java():
    print("Checking Java version...")
    try:
        result = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr + result.stdout
        match = re.search(r'version "(\d+)\.', output)
        if match:
            ver = int(match.group(1))
            print(f"Found Java version: {ver}")
            if ver >= 21:
                return "java"
    except:
        pass
    
    # Check common manual install path for Adoptium on Mac
    manual_path = Path("/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java")
    if manual_path.exists():
        return str(manual_path)
        
    return None

def install_java():
    print("\n--- INSTALLING JAVA 21 (Required) ---")
    
    # Detect Architecture (M1/M2 vs Intel)
    arch = platform.machine()
    if arch == "arm64":
        print("Detected Apple Silicon (M1/M2/M3)")
        url = JAVA_ARM64_URL
    else:
        print("Detected Intel Mac")
        url = JAVA_X64_URL
        
    pkg_path = download_file(url, TEMP_DIR, "java_installer.pkg")
    if not pkg_path: return None

    print("Installing Java... (You will be asked for your password)")
    try:
        # 'installer' command requires sudo/root
        # This will prompt the user for their password in the terminal
        subprocess.run(["sudo", "installer", "-pkg", str(pkg_path), "-target", "/"], check=True)
        print("Java installed successfully.")
        return "java" # Should be in path now
    except subprocess.CalledProcessError:
        print("Java installation failed. Did you enter the correct password?")
        return None

def install_neoforge(java_cmd):
    print("\n--- INSTALLING NEOFORGE ---")
    installer_path = download_file(NEOFORGE_URL, TEMP_DIR)
    if not installer_path: return

    print("Running NeoForge installer...")
    try:
        subprocess.run([java_cmd, "-jar", str(installer_path), "--installClient"], check=True)
        print("NeoForge installed.")
    except:
        print("NeoForge install failed.")

def sync_mods():
    print("\n--- SYNCING MODS ---")
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FOLDER}"
    try:
        r = requests.get(api_url)
        r.raise_for_status()
        files = r.json()
        
        if not MODS_DIR.exists():
            MODS_DIR.mkdir(parents=True)

        for item in files:
            if item['name'].endswith('.jar'):
                dest = MODS_DIR / item['name']
                if not dest.exists():
                    download_file(item['download_url'], MODS_DIR, item['name'])
                else:
                    print(f"Skipping {item['name']} (Already exists)")
    except Exception as e:
        print(f"Mod sync failed: {e}")

def main():
    print("=== MAC MOD INSTALLER ===")
    
    if not TEMP_DIR.exists(): TEMP_DIR.mkdir(parents=True)

    java_cmd = check_java()
    if not java_cmd:
        java_cmd = install_java()
        if not java_cmd:
            print("Critical Error: Java 21 could not be installed.")
            sys.exit(1)

    install_neoforge(java_cmd)
    sync_mods()

    try: shutil.rmtree(TEMP_DIR)
    except: pass
    
    print("\nInstallation Complete!")

if __name__ == "__main__":

    main()
