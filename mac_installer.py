import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import os
import shutil
import sys
import subprocess
import requests
import re
import platform
from pathlib import Path

# --- CONFIGURATION ---
GITHUB_REPO = "KZO999/mods"
GITHUB_FOLDER = ""
NEOFORGE_VERSION = "21.1.215"
MC_VERSION = "1.21.1"
NEOFORGE_URL = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{NEOFORGE_VERSION}/neoforge-{NEOFORGE_VERSION}-installer.jar"

# Java Links
JAVA_ARM64_URL = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_aarch64_mac_hotspot_21.0.5_11.pkg"
JAVA_X64_URL = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_x64_mac_hotspot_21.0.5_11.pkg"

# Paths (Mac Specific)
USER_HOME = Path.home()
MINECRAFT_DIR = USER_HOME / "Library" / "Application Support" / "minecraft"
MODS_DIR = MINECRAFT_DIR / "mods"
TEMP_DIR = Path("/tmp/mod_installer")

class InstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KZO999 Mod Installer (Mac)")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        # Header
        header_label = ttk.Label(root, text="Minecraft Mod Installer", font=("Helvetica", 18, "bold"))
        header_label.pack(pady=10)

        sub_label = ttk.Label(root, text=f"NeoForge {NEOFORGE_VERSION} + Mods", font=("Helvetica", 12))
        sub_label.pack(pady=(0, 10))

        # Progress Bar
        self.progress = ttk.Progressbar(root, orient="horizontal", length=550, mode="indeterminate")
        self.progress.pack(pady=5)

        # Status Label
        self.status_var = tk.StringVar(value="Ready to install")
        self.status_label = ttk.Label(root, textvariable=self.status_var, font=("Helvetica", 10))
        self.status_label.pack(pady=5)

        # Log Area
        self.log_area = scrolledtext.ScrolledText(root, width=70, height=15, state='disabled', font=("Menlo", 10))
        self.log_area.pack(pady=10, padx=10)

        # Install Button
        self.install_btn = ttk.Button(root, text="Start Installation", command=self.start_thread)
        self.install_btn.pack(pady=10)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        if "\n" not in message:
            self.status_var.set(message)

    def start_thread(self):
        self.install_btn.config(state='disabled')
        self.progress.start(10)
        threading.Thread(target=self.run_installation, daemon=True).start()

    def run_installation(self):
        try:
            if not TEMP_DIR.exists(): TEMP_DIR.mkdir(parents=True, exist_ok=True)

            # 1. Java Check
            self.log("--- Checking Java ---")
            java_cmd = self.check_java()
            
            if not java_cmd:
                self.log("Java 21 missing. Installing...", "blue")
                java_cmd = self.install_java()
                if not java_cmd:
                    raise Exception("Failed to install Java 21.")

            # 2. Check Vanilla Minecraft
            self.log(f"--- Checking for Minecraft {MC_VERSION} ---")
            if not self.check_vanilla_mc():
                raise Exception(f"Minecraft {MC_VERSION} not found.\nPlease open the Launcher and play version {MC_VERSION} once.")

            # 3. NeoForge
            self.log("\n--- Installing NeoForge ---")
            self.install_neoforge(java_cmd)

            # 4. Mods
            self.log("\n--- Syncing Mods ---")
            self.sync_mods()

            # Cleanup
            try: shutil.rmtree(TEMP_DIR)
            except: pass

            self.log("\nSUCCESS! Installation Complete.")
            messagebox.showinfo("Success", "Installation Complete!\nSelect the NeoForge profile in your launcher.")

        except Exception as e:
            self.log(f"\nERROR: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.progress.stop()
            self.install_btn.config(state='normal')
            self.status_var.set("Finished")

    # --- LOGIC ---

    def download_file(self, url, dest_folder, filename=None):
        if not filename: filename = url.split('/')[-1]
        dest_path = dest_folder / filename
        self.log(f"Downloading: {filename}...")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        try:
            with requests.get(url, stream=True, headers=headers) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return dest_path
        except Exception as e:
            self.log(f"Download failed: {e}")
            return None

    def check_java(self):
        try:
            result = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stderr + result.stdout
            match = re.search(r'version "(\d+)\.', output)
            if match and int(match.group(1)) >= 21:
                self.log(f"Found compatible Java.")
                return "java"
        except: pass
        
        manual_path = Path("/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java")
        if manual_path.exists():
            return str(manual_path)
        return None

    def check_vanilla_mc(self):
        # On Mac, versions are in ~/Library/Application Support/minecraft/versions
        version_dir = MINECRAFT_DIR / "versions" / MC_VERSION
        version_json = version_dir / f"{MC_VERSION}.json"
        
        if version_json.exists():
            self.log(f"Found Minecraft {MC_VERSION}.")
            return True
        return False

    def install_java(self):
        arch = platform.machine()
        url = JAVA_ARM64_URL if arch == "arm64" else JAVA_X64_URL
        
        pkg_path = self.download_file(url, TEMP_DIR, "java_installer.pkg")
        if not pkg_path: return None

        self.log("Installing Java (Password required)...")
        # On Mac, graphical apps usually cannot capture sudo password input easily in log area.
        # We will use osascript to prompt for password natively.
        install_cmd = f'installer -pkg "{pkg_path}" -target /'
        script = f'do shell script "{install_cmd}" with administrator privileges'
        
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            self.log("Java installed.")
            return self.check_java()
        except subprocess.CalledProcessError:
            self.log("Java installation cancelled or failed.")
            return None

    def install_neoforge(self, java_cmd):
        neoforge_dir = MINECRAFT_DIR / "versions" / f"neoforge-{NEOFORGE_VERSION}"
        if neoforge_dir.exists():
            self.log(f"NeoForge {NEOFORGE_VERSION} found. Skipping.")
            return

        installer_path = self.download_file(NEOFORGE_URL, TEMP_DIR)
        if not installer_path: return

        try:
            self.log("Running NeoForge installer...")
            subprocess.run([java_cmd, "-jar", str(installer_path), "--installClient"], check=True)
            self.log("NeoForge installed.")
        except Exception as e:
            self.log(f"NeoForge install error: {e}")

    def sync_mods(self):
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FOLDER}"
        try:
            r = requests.get(api_url)
            if r.status_code == 404: raise Exception("Repo not found")
            files = r.json()
            
            if not MODS_DIR.exists(): MODS_DIR.mkdir(parents=True)

            for item in files:
                if item['name'].endswith('.jar'):
                    dest = MODS_DIR / item['name']
                    if not dest.exists():
                        self.download_file(item['download_url'], MODS_DIR, item['name'])
                    else:
                        self.log(f"Skipping {item['name']} (Exists)")
        except Exception as e:
            self.log(f"Mod sync failed: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()
