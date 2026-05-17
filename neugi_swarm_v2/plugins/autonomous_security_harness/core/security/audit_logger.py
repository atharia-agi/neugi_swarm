"""
Immutable Audit Logger for Autonomous Security Harness.
Provides write-once, append-only audit trail with hash chaining.
"""
import json, hashlib, logging
from pathlib import Path
from datetime import UTC, datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ImmutableAuditLogger:
    def __init__(self, log_path: str):
        """
        Initialize the audit logger.
        
        Args:
            log_path: Path to the audit log file.
        """
        self.log_path = Path(log_path).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = None
        # If the log file exists, we need to read the last hash to continue the chain.
        if self.log_path.exists():
            try:
                with open(self.log_path, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        if last_line:
                            last_entry = json.loads(last_line)
                            self._last_hash = last_entry.get('_hash')
            except Exception as e:
                logger.warning(f"Could not read last hash from audit log: {e}")
                self._last_hash = None

    def log(self, entry: Dict[str, Any]) -> None:
        """
        Write an audit entry with hash chaining.
        
        Args:
            entry: Dictionary to log (will be JSON serialized).
        """
        # Create a copy of the entry to avoid modifying the original
        entry_to_log = entry.copy()
        # Add timestamp if not present
        if 'timestamp' not in entry_to_log:
            entry_to_log['timestamp'] = datetime.now(UTC).isoformat()
        
        # Convert entry to JSON string for hashing
        entry_str = json.dumps(entry_to_log, sort_keys=True)
        
        # Compute hash of the entry
        entry_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        
        # Create the chained entry
        chained_entry = {
            **entry_to_log,
            '_hash': entry_hash,
            '_prev_hash': self._last_hash
        }
        
        # Append to the log file (atomic write)
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(chained_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")
            raise
        
        # Update the last hash
        self._last_hash = entry_hash
    
    def verify_chain(self) -> bool:
        """
        Verify the integrity of the hash chain in the audit log.
        
        Returns:
            True if the chain is valid, False otherwise.
        """
        if not self.log_path.exists():
            # No log file, so no chain to verify
            return True
        
        prev_hash = None
        try:
            with open(self.log_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in audit log at line {line_num}: {e}")
                        return False
                    
                    # Check the hash chain
                    if entry.get('_prev_hash') != prev_hash:
                        logger.error(f"Hash chain broken at line {line_num}")
                        return False
                    
                    # Verify the entry's hash
                    entry_copy = entry.copy()
                    stored_hash = entry_copy.pop('_hash', None)
                    prev_hash_entry = entry_copy.pop('_prev_hash', None)
                    # Recompute hash
                    entry_str = json.dumps(entry_copy, sort_keys=True)
                    computed_hash = hashlib.sha256(entry_str.encode()).hexdigest()
                    if stored_hash != computed_hash:
                        logger.error(f"Hash mismatch at line {line_num}")
                        return False
                    
                    # Update prev_hash for next iteration
                    prev_hash = stored_hash
        except Exception as e:
            logger.error(f"Error reading audit log for verification: {e}")
            return False
        
        return True
