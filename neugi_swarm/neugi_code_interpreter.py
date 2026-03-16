#!/usr/bin/env python3
"""
🤖 NEUGI CODE INTERPRETER
===========================

Sandboxed code execution:
- Python execution
- JavaScript execution
- Safe environment
- Output capture

Version: 1.0
Date: March 16, 2026
"""

import os
import io
import json
import traceback
import subprocess
from typing import Dict, Any
from contextlib import redirect_stdout, redirect_stderr


class CodeInterpreter:
    """Safe code interpreter with sandboxing"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.globals = {}
        self.locals = {}
        self._setup_environment()

    def _setup_environment(self):
        """Setup safe environment"""
        safe_builtins = {
            "print": print,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "pow": pow,
            "divmod": divmod,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "type": type,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "slice": slice,
            "ord": ord,
            "chr": chr,
            "hex": hex,
            "oct": oct,
            "bin": bin,
            "all": all,
            "any": any,
            "help": help,
            "dir": dir,
            "vars": vars,
            "id": id,
            "hash": hash,
            "input": lambda x: input(x) if x else input(),
        }

        safe_modules = {
            "json": json,
            "math": __import__("math"),
            "random": __import__("random"),
            "datetime": __import__("datetime"),
            "re": __import__("re"),
            "collections": __import__("collections"),
            "itertools": __import__("itertools"),
            "functools": __import__("functools"),
            "operator": __import__("operator"),
            "os": None,
            "sys": None,
            "subprocess": None,
            "socket": None,
        }

        self.globals = {"__builtins__": safe_builtins}

        for name, module in safe_modules.items():
            if module:
                self.globals[name] = module

    def execute_python(self, code: str) -> Dict[str, Any]:
        """Execute Python code safely"""
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = {
            "success": False,
            "output": "",
            "error": None,
            "return_value": None,
            "execution_time": 0,
        }

        import time

        start_time = time.time()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, self.globals, self.locals)

            result["success"] = True
            result["output"] = stdout_capture.getvalue()
            if stderr_capture.getvalue():
                result["output"] += "\n" + stderr_capture.getvalue()

        except Exception as e:
            result["error"] = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
            result["output"] = stderr_capture.getvalue()

        result["execution_time"] = time.time() - start_time
        return result

    def execute_javascript(self, code: str) -> Dict[str, Any]:
        """Execute JavaScript code"""
        try:
            import subprocess

            result = subprocess.run(
                ["node", "-e", code], capture_output=True, text=True, timeout=self.timeout
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "return_code": result.returncode,
            }
        except FileNotFoundError:
            return {"success": False, "error": "Node.js not installed"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timeout"}

    def execute_shell(self, command: str) -> Dict[str, Any]:
        """Execute shell command (restricted)"""
        blocked = ["rm -rf", "dd", "mkfs", "> /dev/", "chmod 777", "sudo", "su -"]

        for cmd in blocked:
            if cmd in command:
                return {"success": False, "error": f"Command blocked: {cmd}"}

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=self.timeout
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timeout"}

    def execute_sql(self, query: str, db_path: str = None) -> Dict[str, Any]:
        """Execute SQL query"""
        import sqlite3

        if db_path is None:
            db_path = os.path.expanduser("~/neugi/neugi.db")

        if not os.path.exists(db_path):
            return {"success": False, "error": "Database not found"}

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            if query.strip().upper().startswith("SELECT"):
                cursor.execute(query)
                results = cursor.fetchall()
                columns = (
                    [description[0] for description in cursor.description]
                    if cursor.description
                    else []
                )

                conn.close()

                return {
                    "success": True,
                    "columns": columns,
                    "rows": results,
                    "row_count": len(results),
                }
            else:
                cursor.execute(query)
                conn.commit()
                row_count = cursor.rowcount
                conn.close()

                return {"success": True, "row_count": row_count}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset(self):
        """Reset interpreter state"""
        self.locals = {}
        self._setup_environment()


class NotebookManager:
    """Interactive notebook manager"""

    def __init__(self):
        self.cells = []
        self.interpreter = CodeInterpreter()

    def add_cell(self, code: str, language: str = "python") -> Dict:
        """Add code cell"""
        cell = {
            "id": len(self.cells),
            "code": code,
            "language": language,
            "output": None,
            "error": None,
        }

        if language == "python":
            result = self.interpreter.execute_python(code)
            cell["output"] = result.get("output")
            cell["error"] = result.get("error")
        elif language == "javascript":
            result = self.interpreter.execute_javascript(code)
            cell["output"] = result.get("output")
            cell["error"] = result.get("error")

        self.cells.append(cell)
        return cell

    def get_cells(self) -> List[Dict]:
        """Get all cells"""
        return self.cells

    def clear(self):
        """Clear all cells"""
        self.cells = []
        self.interpreter.reset()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Code Interpreter")
    parser.add_argument("--python", type=str, help="Execute Python code")
    parser.add_argument("--javascript", type=str, help="Execute JavaScript code")
    parser.add_argument("--shell", type=str, help="Execute shell command")
    parser.add_argument("--sql", type=str, help="Execute SQL query")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    interpreter = CodeInterpreter()

    if args.python:
        result = interpreter.execute_python(args.python)
        print(result["output"] if result["output"] else "")
        if result["error"]:
            print(f"Error: {result['error']}")

    elif args.javascript:
        result = interpreter.execute_javascript(args.javascript)
        print(result["output"] if result["output"] else "")
        if result["error"]:
            print(f"Error: {result['error']}")

    elif args.shell:
        result = interpreter.execute_shell(args.shell)
        print(result["output"] if result["output"] else "")
        if result["error"]:
            print(f"Error: {result['error']}")

    elif args.sql:
        result = interpreter.execute_sql(args.sql)
        if result["success"]:
            if "rows" in result:
                print(f"Columns: {result['columns']}")
                for row in result["rows"]:
                    print(row)
            else:
                print(f"Affected rows: {result['row_count']}")
        else:
            print(f"Error: {result['error']}")

    elif args.interpreter:
        print("NEUGI Code Interpreter (Python)")
        print("Type 'exit()' to quit\n")

        while True:
            try:
                code = input(">>> ")
                if code.strip() in ["exit", "quit"]:
                    break

                result = interpreter.execute_python(code)

                if result["output"]:
                    print(result["output"])
                if result["error"]:
                    print(f"Error: {result['error']}")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    else:
        print("NEUGI Code Interpreter")
        print(
            "Usage: python -m neugi_code_interpreter [--python CODE] [--javascript CODE] [--shell CMD] [--sql QUERY] [--interactive]"
        )


if __name__ == "__main__":
    main()
