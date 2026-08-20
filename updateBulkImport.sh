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

declare -A map
declare -A seen_csv2
declare -A seen_csv1
missing_in_csv1=()

# -----------------------------
# Load CSV2 (mapping list)
# -----------------------------
t0=$(date +%s)

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

    map["$deveui"]="$tags"
    seen_csv2["$deveui"]=1
done < "$CSV2"

t1=$(date +%s)
ts_load_csv2=$((t1 - t0))

# -----------------------------
# Process CSV1 (serial, safe)
# -----------------------------
t0=$(date +%s)

> "$OUT"

while IFS= read -r line || [[ -n "$line" ]]; do
    # Extract DevEUI from column 2
    deveui_raw=$(echo "$line" | cut -d',' -f2)
    deveui=$(sanitize "$deveui_raw")

    if [[ -n "$deveui" && -v map[$deveui] ]]; then
        # Replace ALL occurrences of TUTU with the mapped tag
        tag="${map[$deveui]}"
        line="${line//TUTU/$tag}"
        seen_csv1["$deveui"]=1
        echo "$line" >> "$OUT"
    else
        # DevEUI not found in mapping → mark as missing
        if [[ -n "$deveui" ]]; then
            missing_in_csv1+=("$deveui")
            seen_csv1["$deveui"]=1
        fi
        # ⚠️ Do NOT echo the line if DevEUI missing in CSV2
    fi
done < "$CSV1"

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
    echo "DevEUIs in CSV1 but not found in CSV2 (removed from output) → $FILE"
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
echo "Process CSV1 (serial): ${ts_process_csv1}s"
echo "Generate reports: ${ts_reports}s"
echo "Total runtime: ${total}s"
echo "-----------------------------"

