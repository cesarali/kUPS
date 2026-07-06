#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/moltemplate_files"

rm -f ../system.data ../system.in* ../warning*.txt ../log.*
rm -f system.data system.in* warning*.txt log.* run.in.EXAMPLE
rm -rf output_ttree

moltemplate.sh system.lt

mv -f system.data system.in* ../
rm -rf output_ttree
rm -f run.in.EXAMPLE
mv -f warning*.txt ../ 2>/dev/null || true
mv -f log.* ../ 2>/dev/null || true
