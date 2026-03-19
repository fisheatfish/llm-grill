# VHS demo script — https://github.com/charmbracelet/vhs
# Run: vhs docs/demo.tape

Output docs/demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 1000
Set Height 550
Set Padding 20

Type "# llm-grill — LLM inference benchmark CLI"
Enter
Sleep 500ms

Type "# 1. Check the scenario"
Enter
Sleep 500ms

Type "llm-grill show-scenario scenarios/example.yaml"
Enter
Sleep 3s

Type "# 2. Ping the backend"
Enter
Sleep 500ms

Type "llm-grill ping scenarios/example.yaml"
Enter
Sleep 3s

Type "# 3. Run the benchmark"
Enter
Sleep 500ms

Type "llm-grill run scenarios/example.yaml --output results.jsonl"
Enter
Sleep 12s

Type "# 4. Generate a report"
Enter
Sleep 500ms

Type "llm-grill report results.jsonl"
Enter
Sleep 5s
