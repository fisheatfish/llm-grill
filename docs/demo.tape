# VHS demo script — https://github.com/charmbracelet/vhs
# Run: vhs docs/demo.tape
#
# Prerequisites:
#   1. Install VHS locally: https://github.com/charmbracelet/vhs#installation
#   2. If llm-grill runs on a remote server (e.g. the backends are not reachable
#      from your local machine), create a wrapper script (e.g. scripts/wrapper.sh):
#
#        #!/bin/bash
#        ssh -t your-host "cd /path/to/repo && PATH=/root/.local/bin:\$PATH TERM=xterm-256color llm-grill $*" 2>/dev/null
#
#      - `-t` forces a TTY so Rich outputs colors
#      - `TERM=xterm-256color` ensures 256-color support
#      - `2>/dev/null` suppresses SSH "Connection closed" messages
#
#   3. Make it executable and symlink it (use absolute path!):
#        chmod +x scripts/wrapper.sh
#        sudo ln -sf "$(pwd)/scripts/wrapper.sh" /usr/local/bin/llm-grill
#
#   4. Make sure no local llm-grill shadows the symlink:
#        uv tool uninstall llm-grill   # if installed via uv tool
#        which -a llm-grill            # should show /usr/local/bin/llm-grill only

Output docs/demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 13
Set Width 1000
Set Height 550
Set Padding 20

Type "# llm-grill — LLM inference benchmark CLI"
Enter
Sleep 500ms

Type "# 1. Check the scenario"
Enter
Sleep 500ms

Type "llm-grill show-scenario scenarios/demo.yaml"
Enter
Sleep 3s

Type "# 2. Ping the backend"
Enter
Sleep 500ms

Type "llm-grill ping scenarios/demo.yaml"
Enter
Sleep 3s

Type "# 3. Run the benchmark"
Enter
Sleep 500ms

Type "llm-grill run scenarios/demo.yaml --output results.jsonl"
Enter
Sleep 15s
