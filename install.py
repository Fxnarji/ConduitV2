import os
import shutil
import zipfile
import subprocess
import requests


class BlenderInstaller:
    """Manages downloading, installing, and configuring Blender."""
    
    BASE_URL = "https://download.blender.org/release"
    BLENDER_EXECUTABLE = "blender.exe"
    PORTABLE_SUBDIRS = ["autosaves", "extensions", "config", "scripts"]
    
    def __init__(self, version, platform, install_directory):
        """
        Initialize the Blender installer.
        
        Args:
            version: List of version numbers [major, minor, patch]
            platform: Platform string (e.g., "windows-x64")
            install_directory: Directory to install Blender
        """
        self.version = version
        self.platform = platform
        self.install_directory = install_directory
        self.version_str = ".".join(map(str, version))
        self.dirname = f"blender-{self.version_str}-{platform}"
        self.url = f"{self.BASE_URL}/Blender{version[0]}.{version[1]}/{self.dirname}.zip"
        self.blender_dir = os.path.join(install_directory, self.dirname)
        self.zip_path = os.path.join(install_directory, f"{self.dirname}.zip")
        self.exec_path = os.path.join(self.blender_dir, self.BLENDER_EXECUTABLE)

    def download_blender(self):
        """Download Blender from the official repository."""
        print(f"Downloading from {self.url}...")
        response = requests.get(self.url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(self.zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size and downloaded % (1 * 1024 * 1024) == 0:  # Every 50 MB
                        mb_downloaded = downloaded / 1024 / 1024
                        mb_total = total_size / 1024 / 1024
                        print(f"  {mb_downloaded:.1f} MB / {mb_total:.1f} MB")
        
        print(f"Downloaded to {self.zip_path}")

    def unzip_blender(self):
        """Extract Blender archive and remove the zip file."""
        print(f"Extracting {self.zip_path}...")
        
        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            members = zip_ref.namelist()
            for i, member in enumerate(members, 1):
                zip_ref.extract(member, self.install_directory)
                if i % 100 == 0:  # Print every 100 files
                    print(f"  {i}/{len(members)} files extracted")
        
        os.remove(self.zip_path)
        print("Extraction complete")


    def isolate_blender_prefs(self):
        """Create portable configuration directories for Blender."""
        portable_dir = os.path.join(self.blender_dir, "portable")
        
        for subdir in self.PORTABLE_SUBDIRS:
            os.makedirs(os.path.join(portable_dir, subdir), exist_ok=True)
        
        print(f"Created portable configuration at {portable_dir}")

    def add_app_template(self, template_source_dir):
        """
        Copy app template to Blender installation.
        
        Args:
            template_source_dir: Path to the source template directory
        """
        template_dest = os.path.join(
            self.blender_dir,
            self.version_str.rsplit(".", 1)[0],  # Major.minor version
            "scripts", "startup", "bl_app_templates_system", "conduit"
        )
        os.makedirs(template_dest, exist_ok=True)
        
        for item in os.listdir(template_source_dir):
            source = os.path.join(template_source_dir, item)
            destination = os.path.join(template_dest, item)
            
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
        
        print(f"App template copied to {template_dest}")

    def launch_blender(self, app_template="conduit"):
        """
        Launch Blender with specified app template.
        
        Args:
            app_template: Name of the app template to use
        """
        print(f"Launching Blender with '{app_template}' template...")
        subprocess.run([self.exec_path, "--app-template", app_template])


def main():
    """Main execution function."""
    # Configuration
    version = [5, 0, 1]
    platform = "windows-x64"
    root = r"C:\Users\Fxnarji\Documents\Testing\blender_git_test"
    install_directory = os.path.join(root, "02-ressources", "blender-installs")
    template_source = os.path.join(root, "02-ressources", "blender_app_template")
    
    # Create installer and run setup
    installer = BlenderInstaller(version, platform, install_directory)
    
    print("Starting Blender installation...")
    installer.download_blender()
    installer.unzip_blender()
    installer.isolate_blender_prefs()
    installer.add_app_template(template_source)
    installer.launch_blender()
    print("Installation complete!")


if __name__ == "__main__":
    main()
