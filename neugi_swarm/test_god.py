import os
import sys
sys.path.append(r"k:\neugi\neugi_swarm")
os.environ["NEUGI_GOD_MODE"] = "1"
from neugi_swarm_tools import ToolManager
tm = ToolManager()
res = tm.execute("code_execute", code="wsl -u mikael whoami", language="bash")
print(res)
