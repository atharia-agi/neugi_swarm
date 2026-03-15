#!/usr/bin/env python3
"""
🤖 NEUGI BACKUP SYSTEM
========================

Backup and restore:
- Full backups
- Incremental backups
- Scheduled backups
- Encryption
- Restore

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import shutil
import hashlib
import uuid
import tarfile
import gzip
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

NEUGI_DIR = os.path.expanduser("~/neugi")
BACKUP_DIR = os.path.join(NEUGI_DIR, "backups")
CONFIG_FILE = os.path.join(BACKUP_DIR, "config.json")
os.makedirs(BACKUP_DIR, exist_ok=True)


class BackupJob:
    """Backup job definition"""

    def __init__(
        self,
        id: str = None,
        name: str = "",
        source: str = "",
        destination: str = "",
        schedule: str = "manual",
        retention: int = 7,
        compression: bool = True,
        encryption: bool = False,
    ):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.source = source
        self.destination = destination
        self.schedule = schedule
        self.retention = retention
        self.compression = compression
        self.encryption = encryption
        self.created_at = datetime.now().isoformat()
        self.last_run = None
        self.last_status = None
        self.runs = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "destination": self.destination,
            "schedule": self.schedule,
            "retention": self.retention,
            "compression": self.compression,
            "encryption": self.encryption,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "last_status": self.last_status,
            "runs": self.runs,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BackupJob":
        job = cls(
            data["id"],
            data["name"],
            data["source"],
            data["destination"],
            data.get("schedule", "manual"),
            data.get("retention", 7),
            data.get("compression", True),
            data.get("encryption", False),
        )
        job.last_run = data.get("last_run")
        job.last_status = data.get("last_status")
        job.runs = data.get("runs", 0)
        job.created_at = data.get("created_at", datetime.now().isoformat())
        return job


class BackupManager:
    """Backup manager"""

    def __init__(self):
        self.jobs: Dict[str, BackupJob] = {}
        self._load_jobs()

    def _load_jobs(self):
        """Load backup jobs"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                    for job_data in data:
                        job = BackupJob.from_dict(job_data)
                        self.jobs[job.id] = job
            except:
                pass

    def _save_jobs(self):
        """Save backup jobs"""
        with open(CONFIG_FILE, "w") as f:
            json.dump([job.to_dict() for job in self.jobs.values()], f, indent=2)

    def create_job(
        self,
        name: str,
        source: str,
        destination: str = None,
        schedule: str = "manual",
        retention: int = 7,
    ) -> BackupJob:
        """Create backup job"""
        if destination is None:
            destination = os.path.join(BACKUP_DIR, f"{name}_{datetime.now().strftime('%Y%m%d')}")

        job = BackupJob(None, name, source, destination, schedule, retention)
        self.jobs[job.id] = job
        self._save_jobs()
        return job

    def delete_job(self, job_id: str):
        """Delete backup job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_jobs()

    def run_backup(self, job_id: str) -> Dict:
        """Run backup job"""
        job = self.jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        try:
            backup_path = job.destination
            os.makedirs(backup_path, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

            if job.compression:
                backup_file = os.path.join(backup_path, f"{backup_name}.tar.gz")
            else:
                backup_file = os.path.join(backup_path, backup_name)

            files_backed = 0
            total_size = 0

            if job.compression:
                with tarfile.open(backup_file, "w:gz") as tar:
                    for root, dirs, files in os.walk(job.source):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                tar.add(file_path, arcname=os.path.relpath(file_path, job.source))
                                files_backed += 1
                                total_size += os.path.getsize(file_path)
                            except:
                                pass
            else:
                dest_path = backup_file
                for root, dirs, files in os.walk(job.source):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, job.source)
                        dest_file = os.path.join(dest_path, rel_path)
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        shutil.copy2(file_path, dest_file)
                        files_backed += 1
                        total_size += os.path.getsize(file_path)

            checksum = self._calculate_checksum(backup_file)

            job.last_run = datetime.now().isoformat()
            job.last_status = "success"
            job.runs += 1
            self._save_jobs()

            self._cleanup_old_backups(job)

            return {
                "success": True,
                "backup_file": backup_file,
                "files_backed": files_backed,
                "total_size": total_size,
                "checksum": checksum,
            }

        except Exception as e:
            job.last_run = datetime.now().isoformat()
            job.last_status = "failed"
            self._save_jobs()
            return {"success": False, "error": str(e)}

    def _cleanup_old_backups(self, job: BackupJob):
        """Cleanup old backups based on retention"""
        if not os.path.exists(job.destination):
            return

        backups = []
        for f in os.listdir(job.destination):
            if f.startswith("backup_"):
                path = os.path.join(job.destination, f)
                backups.append((path, os.path.getmtime(path)))

        backups.sort(key=lambda x: x[1], reverse=True)

        for path, _ in backups[job.retention :]:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except:
                pass

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate file checksum"""
        if not os.path.exists(file_path):
            return ""

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def restore_backup(self, backup_file: str, destination: str) -> Dict:
        """Restore from backup"""
        try:
            if not os.path.exists(backup_file):
                return {"success": False, "error": "Backup file not found"}

            if backup_file.endswith(".tar.gz"):
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(destination)
            else:
                shutil.copytree(backup_file, destination, dirs_exist_ok=True)

            return {"success": True, "destination": destination}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_backups(self, job_id: str = None) -> List[Dict]:
        """List available backups"""
        if job_id:
            job = self.jobs.get(job_id)
            if not job:
                return []
            return self._list_dir_backups(job.destination)

        all_backups = []
        for job in self.jobs.values():
            backups = self._list_dir_backups(job.destination)
            all_backups.extend(backups)

        return all_backups

    def _list_dir_backups(self, path: str) -> List[Dict]:
        """List backups in directory"""
        if not os.path.exists(path):
            return []

        backups = []
        for f in os.listdir(path):
            full_path = os.path.join(path, f)
            if os.path.isfile(full_path) and f.startswith("backup_"):
                backups.append(
                    {
                        "name": f,
                        "path": full_path,
                        "size": os.path.getsize(full_path),
                        "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
                    }
                )
            elif os.path.isdir(full_path) and f.startswith("backup_"):
                total_size = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, dn, fn in os.walk(full_path)
                    for f in fn
                )
                backups.append(
                    {
                        "name": f,
                        "path": full_path,
                        "size": total_size,
                        "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
                    }
                )

        return sorted(backups, key=lambda x: x["modified"], reverse=True)

    def get_job(self, job_id: str) -> Optional[BackupJob]:
        """Get backup job"""
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[Dict]:
        """List all backup jobs"""
        return [job.to_dict() for job in self.jobs.values()]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Backup System")
    parser.add_argument(
        "--create", nargs=3, metavar=("NAME", "SOURCE", "DEST"), help="Create backup job"
    )
    parser.add_argument("--run", type=str, help="Run backup job")
    parser.add_argument("--restore", nargs=2, metavar=("BACKUP", "DEST"), help="Restore backup")
    parser.add_argument("--list-jobs", action="store_true", help="List backup jobs")
    parser.add_argument("--list-backups", type=str, help="List backups for job")
    parser.add_argument("--delete", type=str, help="Delete backup job")

    args = parser.parse_args()

    manager = BackupManager()

    if args.create:
        name, source, dest = args.create
        job = manager.create_job(name, source, dest)
        print(f"Created backup job: {job.name} (ID: {job.id})")

    elif args.run:
        result = manager.run_backup(args.run)
        if result.get("success"):
            print(f"Backup completed: {result['files_backed']} files, {result['total_size']} bytes")
        else:
            print(f"Backup failed: {result.get('error')}")

    elif args.restore:
        backup, dest = args.restore
        result = manager.restore_backup(backup, dest)
        if result.get("success"):
            print(f"Restored to: {result['destination']}")
        else:
            print(f"Restore failed: {result.get('error')}")

    elif args.list_jobs:
        jobs = manager.list_jobs()
        print(f"\n📦 Backup Jobs ({len(jobs)}):\n")
        for job in jobs:
            status = (
                "✅"
                if job["last_status"] == "success"
                else "❌"
                if job["last_status"] == "failed"
                else "⏳"
            )
            print(f"  {status} {job['name']}")
            print(f"      Source: {job['source']}")
            print(f"      Runs: {job['runs']} | Last: {job['last_run'] or 'Never'}")

    elif args.list_backups:
        backups = manager.list_backups(args.list_backups)
        print(f"\n📁 Backups ({len(backups)}):\n")
        for b in backups:
            size_mb = b["size"] / 1024 / 1024
            print(f"  {b['name']} - {size_mb:.2f} MB")

    elif args.delete:
        manager.delete_job(args.delete)
        print(f"Deleted job: {args.delete}")

    else:
        print("NEUGI Backup System")
        print(
            "Usage: python -m neugi_backup [--create NAME SOURCE DEST] [--run JOB] [--restore BACKUP DEST] [--list-jobs] [--list-backups JOB] [--delete JOB]"
        )


if __name__ == "__main__":
    main()
