#!/usr/bin/env bash
# Run Codex once per item (round 4), each with its reference images attached.
cd "D:/Airis/Projects/Pet/Cereberus" || exit 1
CODEX=/c/Users/Raven/AppData/Local/OpenAI/Codex/bin/a159911ff70742e9/codex.exe
mkdir -p art/codex/logs
while IFS='|' read -r name images; do
  [ -z "$name" ] && continue
  echo "=== $name $(date +%T)"
  eval "set -- $images"
  echo "Read art/codex/items/$name.md and make exactly that one item under its hard rules. The attached images are the reference character; pass them to the image tool." \
    | "$CODEX" exec --sandbox workspace-write --add-dir "C:/Users/Raven/.codex/generated_images" \
        --skip-git-repo-check -C "D:/Airis/Projects/Pet/Cereberus" "$@" \
        -o "art/codex/logs/${name}_last.txt" - > "art/codex/logs/${name}.log" 2>&1
  echo "    exit $? $(date +%T)"
done < art/codex/items/queue.txt
echo "ALL DONE $(date +%T)"
