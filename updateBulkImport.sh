#!/usr/bin/env bash
set -euo pipefail

CSV1=""
CSV2=""
OUT=""
DEBUG=false

usage() {
    echo "Usage: $0 --csv1 <file> --csv2 <file> --out <output.csv> [--debug]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --csv1) CSV1="$2"; shift 2 ;;
        --csv2) CSV2="$2"; shift 2 ;;
        --out)  OUT="$2"; shift 2 ;;
        --debug) DEBUG=true; shift ;;
        *) usage ;;
    esac
done

[[ -z "$CSV1" || -z "$CSV2" || -z "$OUT" ]] && usage

OUT_DIR="$(dirname "$OUT")"

log_debug() { $DEBUG && echo "[DEBUG] $*"; }

sanitize() {
    echo -n "$1" | tr -d '\r\n\t "' | sed 's/[^a-fA-F0-9]//g'
}

ts_start=$(date +%s)
ts_load_csv2=0
ts_process_csv1=0
ts_reports=0

echo "Script started at: $(date)"

declare -A seen_csv2
declare -A seen_csv1
missing_in_csv1=()

# -----------------------------
# Load CSV2 (mapping list)
# -----------------------------
t0=$(date +%s)

MAPFILE="$OUT_DIR/map.tmp"
: > "$MAPFILE"

while IFS=, read -r deveui tags || [[ -n "$deveui" ]]; do
    deveui=$(sanitize "$deveui")
    [[ -z "$deveui" ]] && continue

    if [[ -z "$tags" || "$tags" == "\"\"" ]]; then
        tags="\"TWA_100057491.79575.AS\""
    elif [[ "$tags" == \"*\" ]]; then
        tags="$tags"
    else
        tags="\"$tags\""
    fi

    seen_csv2["$deveui"]=1
    echo "$deveui,$tags" >> "$MAPFILE"
done < "$CSV2"

t1=$(date +%s)
ts_load_csv2=$((t1 - t0))

CPU_CORES=$(nproc)
WORKERS=$(( CPU_CORES * 2 ))
log_debug "Parallel workers: $WORKERS"

# -----------------------------
# Process CSV1 in parallel
# -----------------------------
t0=$(date +%s)

# Ensure output file is empty WITHOUT writing a blank line
> "$OUT"

export MAPFILE

cat "$CSV1" | \
xargs -P "$WORKERS" -I{} bash -c '
line="$1"

deveui_raw=$(echo "$line" | cut -d"," -f2)
deveui=$(echo -n "$deveui_raw" | tr -d "\r\n\t \"" | sed "s/[^a-fA-F0-9]//g")

tag=$(grep -Fm1 "$deveui," "$MAPFILE" | sed -e "s/^[^,]*,//")

if [[ -n "$tag" ]]; then
    echo "${line//TUTU/$tag}"
else
    echo "__REMOVE__,$deveui"
fi
' _ "{}" > "$OUT.tmp"

while IFS= read -r line; do
    if [[ "$line" == __REMOVE__* ]]; then
        deveui="${line#*,}"
        deveui=$(sanitize "$deveui")
        missing_in_csv1+=("$deveui")
        seen_csv1["$deveui"]=1
    else
        deveui_raw=$(echo "$line" | cut -d"," -f2)
        deveui=$(sanitize "$deveui_raw")
        seen_csv1["$deveui"]=1
        echo "$line" >> "$OUT"
    fi
done < "$OUT.tmp"

rm -f "$OUT.tmp" "$MAPFILE"

t1=$(date +%s)
ts_process_csv1=$((t1 - t0))

# -----------------------------
# Reports
# -----------------------------
t0=$(date +%s)

CSV1_NAME="$(basename "$CSV1" .csv)"
CSV2_NAME="$(basename "$CSV2" .csv)"

if (( ${#missing_in_csv1[@]} > 0 )); then
    FILE="$OUT_DIR/missing_in_${CSV2_NAME}.txt"
    printf '%s\n' "${missing_in_csv1[@]}" > "$FILE"
    echo "DevEUIs in CSV1 but not found in CSV2 (removed) → $FILE"
else
    echo "All DevEUIs in CSV1 were present in CSV2."
fi

missing_in_csv2=()
for d in "${!seen_csv2[@]}"; do
    if [[ -z "${seen_csv1[$d]:-}" ]]; then
        missing_in_csv2+=("$d")
    fi
done

if (( ${#missing_in_csv2[@]} > 0 )); then
    FILE="$OUT_DIR/missing_in_${CSV1_NAME}.txt"
    printf '%s\n' "${missing_in_csv2[@]}" > "$FILE"
    echo "DevEUIs in CSV2 but not found in CSV1 → $FILE"
else
    echo "All DevEUIs in CSV2 were present in CSV1."
fi

t1=$(date +%s)
ts_reports=$((t1 - t0))

# -----------------------------
# Summary
# -----------------------------
ts_end=$(date +%s)
total=$((ts_end - ts_start))

echo "---- Performance Profile ----"
echo "Load CSV2 mapping: ${ts_load_csv2}s"
echo "Process CSV1 (parallel): ${ts_process_csv1}s"
echo "Generate reports: ${ts_reports}s"
echo "Total runtime: ${total}s"
echo "CPU cores: $CPU_CORES"
echo "Parallel workers: $WORKERS"
echo "-----------------------------"

