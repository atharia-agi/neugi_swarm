#!/usr/bin/env python3
"""
🤖 NEUGI FILE MANAGER
=======================

Full-featured file manager:
- Browse directories
- File operations (copy, move, delete)
- Search files
- File preview
- Batch operations

Version: 1.0
Date: March 16, 2026
"""

import os
import shutil
import hashlib
import mimetypes
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

NEUGI_DIR = os.path.expanduser("~/neugi")


class FileManager:
    """Full-featured file manager"""

    def __init__(self, root_dir: str = None):
        self.root_dir = root_dir or os.getcwd()
        self.current_dir = self.root_dir

    def list(self, path: str = None, show_hidden: bool = False) -> List[Dict]:
        """List directory contents"""
        target = path or self.current_dir

        if not os.path.exists(target):
            return [{"error": "Path does not exist"}]

        if not os.path.isdir(target):
            return [{"error": "Not a directory"}]

        items = []

        try:
            for item in os.listdir(target):
                if not show_hidden and item.startswith("."):
                    continue

                full_path = os.path.join(target, item)
                stat = os.stat(full_path)

                item_type = "file"
                if os.path.isdir(full_path):
                    item_type = "directory"
                elif os.path.islink(full_path):
                    item_type = "link"

                items.append(
                    {
                        "name": item,
                        "path": full_path,
                        "type": item_type,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "permissions": oct(stat.st_mode)[-3:],
                    }
                )

            items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

        except PermissionError:
            return [{"error": "Permission denied"}]

        return items

    def get_info(self, path: str) -> Optional[Dict]:
        """Get file/directory info"""
        if not os.path.exists(path):
            return None

        stat = os.stat(path)

        return {
            "name": os.path.basename(path),
            "path": os.path.abspath(path),
            "type": "directory" if os.path.isdir(path) else "file",
            "size": stat.st_size,
            "size_formatted": self._format_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "permissions": oct(stat.st_mode),
            "is_readable": os.access(path, os.R_OK),
            "is_writable": os.access(path, os.W_OK),
            "is_executable": os.access(path, os.X_OK),
        }

    def create_directory(self, path: str) -> Dict:
        """Create directory"""
        try:
            os.makedirs(path, exist_ok=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, path: str, recursive: bool = False) -> Dict:
        """Delete file or directory"""
        try:
            if os.path.isdir(path):
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)
            else:
                os.remove(path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy(self, source: str, destination: str) -> Dict:
        """Copy file or directory"""
        try:
            if os.path.isdir(source):
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
            return {"success": True, "destination": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move(self, source: str, destination: str) -> Dict:
        """Move file or directory"""
        try:
            shutil.move(source, destination)
            return {"success": True, "destination": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename(self, path: str, new_name: str) -> Dict:
        """Rename file or directory"""
        try:
            new_path = os.path.join(os.path.dirname(path), new_name)
            os.rename(path, new_path)
            return {"success": True, "new_path": new_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, path: str, encoding: str = "utf-8", lines: int = None) -> Dict:
        """Read file content"""
        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                if lines:
                    content = "".join(f.readlines()[:lines])
                else:
                    content = f.read()

            return {
                "success": True,
                "content": content,
                "size": len(content),
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict:
        """Write file content"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            return {"success": True, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict:
        """Append to file"""
        try:
            with open(path, "a", encoding=encoding) as f:
                f.write(content)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search(self, query: str, path: str = None, file_types: List[str] = None) -> List[Dict]:
        """Search files"""
        target = path or self.current_dir
        results = []

        for root, dirs, files in os.walk(target):
            for name in files:
                if query.lower() in name.lower():
                    if file_types:
                        ext = os.path.splitext(name)[1]
                        if ext not in file_types:
                            continue

                    full_path = os.path.join(root, name)
                    try:
                        stat = os.stat(full_path)
                        results.append(
                            {
                                "name": name,
                                "path": full_path,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            }
                        )
                    except:
                        pass

        return results[:100]

    def get_hash(self, path: str, algorithm: str = "sha256") -> Dict:
        """Get file hash"""
        try:
            hash_func = getattr(hashlib, algorithm)()

            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)

            return {"success": True, "algorithm": algorithm, "hash": hash_func.hexdigest()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_disk_usage(self, path: str = None) -> Dict:
        """Get disk usage"""
        target = path or self.current_dir

        try:
            usage = shutil.disk_usage(target)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": (usage.used / usage.total) * 100,
            }
        except Exception as e:
            return {"error": str(e)}

    def batch_rename(self, files: List[str], pattern: str, replacement: str) -> List[Dict]:
        """Batch rename files"""
        results = []

        for file_path in files:
            try:
                directory = os.path.dirname(file_path)
                filename = os.path.basename(file_path)
                new_filename = filename.replace(pattern, replacement)
                new_path = os.path.join(directory, new_filename)

                os.rename(file_path, new_path)
                results.append({"original": file_path, "new": new_path, "success": True})
            except Exception as e:
                results.append({"original": file_path, "success": False, "error": str(e)})

        return results

    def _format_size(self, size: int) -> str:
        """Format file size"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def get_type(self, path: str) -> str:
        """Get file type"""
        if os.path.isdir(path):
            return "directory"

        mime_type, _ = mimetypes.guess_type(path)
        if mime_type:
            return mime_type

        ext = os.path.splitext(path)[1]
        return f"file/{ext[1:]}" if ext else "application/octet-stream"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI File Manager")
    parser.add_argument("path", nargs="?", help="Path to list")
    parser.add_argument("--ls", action="store_true", help="List directory")
    parser.add_argument("--info", type=str, help="Get file info")
    parser.add_argument("--search", type=str, help="Search files")
    parser.add_argument("--hash", type=str, help="Get file hash")
    parser.add_argument("--disk", action="store_true", help="Disk usage")

    args = parser.parse_args()

    fm = FileManager()

    if args.ls or args.path:
        items = fm.list(args.path)
        for item in items:
            if "error" in item:
                print(f"Error: {item['error']}")
            else:
                icon = "📁" if item["type"] == "directory" else "📄"
                print(f"{icon} {item['name']}")

    elif args.info:
        info = fm.get_info(args.info)
        if info:
            print(f"\n📄 {info['name']}")
            print(f"   Path: {info['path']}")
            print(f"   Type: {info['type']}")
            print(f"   Size: {info['size_formatted']}")
            print(f"   Modified: {info['modified']}")
        else:
            print("File not found")

    elif args.search:
        results = fm.search(args.search)
        print(f"\n🔍 Search: {args.search}\n")
        for r in results:
            print(f"  📄 {r['name']}")
            print(f"     {r['path']}")

    elif args.hash:
        result = fm.get_hash(args.hash)
        if result.get("success"):
            print(f"{result['algorithm']}: {result['hash']}")
        else:
            print(f"Error: {result.get('error')}")

    elif args.disk:
        usage = fm.get_disk_usage()
        print(f"\n💾 Disk Usage:")
        print(f"   Total: {fm._format_size(usage['total'])}")
        print(f"   Used:  {fm._format_size(usage['used'])}")
        print(f"   Free:  {fm._format_size(usage['free'])}")
        print(f"   Usage: {usage['percent']:.1f}%")

    else:
        print("NEUGI File Manager")
        print(
            "Usage: python -m neugi_file_manager [--ls PATH] [--info FILE] [--search QUERY] [--hash FILE] [--disk]"
        )


if __name__ == "__main__":
    main()
