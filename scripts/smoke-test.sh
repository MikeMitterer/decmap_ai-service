#!/usr/bin/env bash
# ─── AI-Service Smoke Test ────────────────────────────────────────────────────
# Testet alle AI-Service-Endpunkte ohne UI-Workflow.
# Simuliert den vollständigen Directus-Flow: Submit → Approve → Clustering.
#
# Verwendung:
#   smoke-test.sh [OPTIONEN] [BEFEHL]
#
# Befehle:
#   health          Health-Check (default wenn kein Befehl angegeben)
#   similarity      Ähnlichkeits-Check mit Testtext
#   submit          Hook: Problem eingereicht (Spam-Filter + Embedding)
#   submit-bot      Hook: Problem mit Bot-Signalen (→ rejected)
#   submit-honeypot Hook: Problem mit Honeypot (→ sofortiger Reject)
#   approve         Hook: Problem freigegeben (Embedding + AI-Lösung + Clustering)
#   vote            Hook: Vote geändert
#   cluster         Clustering manuell triggern
#   ws              WebSocket-Verbindung öffnen (braucht: brew install websocat)
#   all             Alle Tests sequenziell (ohne ws)
#
# Optionen:
#   --url URL       Basis-URL des AI-Service (Standard: http://localhost:8000)
#   --secret SEC    Webhook-Secret für X-Webhook-Secret Header
#   --id ID         Problem-ID für submit/approve/vote (Standard: smoke-test-001)
#   --help          Diese Hilfe + Hinweise auf weitere Tools anzeigen
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────

BASE_URL="${AI_SERVICE_URL:-http://localhost:8000}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-}"
PROBLEM_ID="smoke-test-001"

# ─── Farben ──────────────────────────────────────────────────────────────────

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

ok()     { echo -e "  ${GREEN}✓${RESET} $1"; }
fail()   { echo -e "  ${RED}✗${RESET} $1" >&2; }
info()   { echo -e "  ${BLUE}→${RESET} $1"; }
header() { echo -e "\n${BOLD}${YELLOW}$1${RESET}"; }
sep()    { echo -e "${CYAN}────────────────────────────────────────${RESET}"; }

die() {
    echo -e "${RED}Fehler: $1${RESET}" >&2
    exit 1
}

require_cmd() {
    command -v "$1" &>/dev/null || die "'$1' nicht gefunden — $2"
}

# Führt curl aus und gibt HTTP-Status + Body aus
do_request() {
    local method="$1"
    local path="$2"
    local body="${3:-}"
    local url="${BASE_URL}${path}"

    local curl_args=(-s -w "\n%{http_code}" -X "$method" "$url" -H "Content-Type: application/json")

    [[ -n "$WEBHOOK_SECRET" ]] && curl_args+=(-H "X-Webhook-Secret: $WEBHOOK_SECRET")
    [[ -n "$body" ]] && curl_args+=(-d "$body")

    local response
    response=$(curl "${curl_args[@]}")

    local http_code
    http_code=$(echo "$response" | tail -1)

    local body_out
    body_out=$(echo "$response" | head -n -1)

    echo "$body_out" | jq . 2>/dev/null || echo "$body_out"
    return_code="$http_code"
}

check_status() {
    local label="$1"
    local expected="$2"
    if [[ "$return_code" == "$expected" ]]; then
        ok "$label (HTTP $return_code)"
    else
        fail "$label — erwartet HTTP $expected, bekommen HTTP $return_code"
    fi
}

# ─── Hilfe ───────────────────────────────────────────────────────────────────

usage() {
    echo ""
    echo -e "${BOLD}${YELLOW}AI-Service Smoke Test${RESET}"
    echo ""
    echo -e "  Testet alle AI-Service-Endpunkte ohne UI-Workflow."
    echo ""
    echo -e "${BOLD}Verwendung:${RESET}"
    echo -e "  $(basename "$0") [OPTIONEN] [BEFEHL]"
    echo ""
    echo -e "${BOLD}Befehle:${RESET}"
    printf "  ${BLUE}%-18s${RESET} %s\n" "health"          "Health-Check (Standard)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "similarity"      "Ähnlichkeits-Check mit Testtext"
    printf "  ${BLUE}%-18s${RESET} %s\n" "submit"          "Hook: Problem eingereicht (Spam-Filter + Embedding)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "submit-bot"      "Hook: Problem mit Bot-Signalen (→ rejected)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "submit-honeypot" "Hook: Problem mit Honeypot (→ sofortiger Reject)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "approve"         "Hook: Problem freigegeben (Embedding + AI-Lösung + Clustering)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "vote"            "Hook: Vote geändert"
    printf "  ${BLUE}%-18s${RESET} %s\n" "cluster"         "Clustering manuell triggern"
    printf "  ${BLUE}%-18s${RESET} %s\n" "ws"              "WebSocket-Verbindung öffnen (braucht: brew install websocat)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "all"             "Alle Tests sequenziell (ohne ws)"
    echo ""
    echo -e "${BOLD}Optionen:${RESET}"
    printf "  ${BLUE}%-18s${RESET} %s\n" "--url URL"       "Basis-URL (Standard: http://localhost:8000)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "--secret SEC"    "Webhook-Secret (oder env: WEBHOOK_SECRET)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "--id ID"         "Problem-ID für submit/approve/vote (Standard: smoke-test-001)"
    printf "  ${BLUE}%-18s${RESET} %s\n" "--help"          "Diese Hilfe anzeigen"
    echo ""
    echo -e "${BOLD}Weitere Tools:${RESET}"
    echo ""
    printf "  ${CYAN}%-30s${RESET} %s\n" "Swagger UI (interaktiv)"  "${BASE_URL}/docs"
    printf "  ${CYAN}%-30s${RESET} %s\n" "ReDoc (Doku)"             "${BASE_URL}/redoc"
    printf "  ${CYAN}%-30s${RESET} %s\n" "OpenAPI-Schema"           "${BASE_URL}/openapi.json"
    printf "  ${CYAN}%-30s${RESET} %s\n" "curl-Beispiele"           "docs/cmdline.md  (im Root-Repo)"
    printf "  ${CYAN}%-30s${RESET} %s\n" "WebSocket live"           "websocat ws://localhost:8000/ws  (brew install websocat)"
    echo ""
    echo -e "${BOLD}Beispiele:${RESET}"
    echo -e "  $(basename "$0") all"
    echo -e "  $(basename "$0") --secret mysecret submit"
    echo -e "  $(basename "$0") --url https://decisionmap.ai/api health"
    echo -e "  AI_SERVICE_URL=http://localhost:8000 WEBHOOK_SECRET=xyz $(basename "$0") all"
    echo ""
}

# ─── Argument-Parsing ────────────────────────────────────────────────────────

COMMAND=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)    BASE_URL="$2";       shift 2 ;;
        --secret) WEBHOOK_SECRET="$2"; shift 2 ;;
        --id)     PROBLEM_ID="$2";     shift 2 ;;
        --help|-h) usage; exit 0 ;;
        health|similarity|submit|submit-bot|submit-honeypot|approve|vote|cluster|ws|all)
            COMMAND="$1"; shift ;;
        *)
            echo -e "${RED}Unbekannte Option: $1${RESET}" >&2
            usage; exit 1 ;;
    esac
done

[[ -z "$COMMAND" ]] && usage && exit 0

require_cmd curl  "curl ist erforderlich"
require_cmd jq    "jq ist erforderlich — brew install jq"

# ─── Test-Befehle ────────────────────────────────────────────────────────────

cmd_health() {
    header "Health-Check"
    sep
    do_request GET /health
    check_status "GET /health" "200"
}

cmd_similarity() {
    header "Similarity-Check"
    sep
    info "Text: 'We have no AI governance framework in our company'"
    do_request POST /similarity '{"text": "We have no AI governance framework in our company"}'
    check_status "POST /similarity" "200"
}

cmd_submit() {
    header "Hook: problem-submitted  (ID: ${PROBLEM_ID})"
    sep
    info "Normales Problem — erwartet: pending oder needs_review"
    do_request POST /hooks/problem-submitted "$(cat <<JSON
{
  "problem_id": "${PROBLEM_ID}",
  "title": "Lack of AI governance framework",
  "description": "Our organization has no clear policies for AI usage, leading to inconsistent and potentially risky deployments.",
  "ip_hash": "abc123def456",
  "signals": [],
  "honeypot": null,
  "submitted_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
JSON
)"
    check_status "POST /hooks/problem-submitted" "200"
}

cmd_submit_bot() {
    header "Hook: problem-submitted  (Bot-Signale → rejected)"
    sep
    info "Zwei Bot-Signale → wird automatisch rejected (kein LLM-Call)"
    do_request POST /hooks/problem-submitted "$(cat <<JSON
{
  "problem_id": "${PROBLEM_ID}-bot",
  "title": "Buy cheap AI tools now!!!",
  "description": "Click here for amazing AI deals",
  "ip_hash": "bot999",
  "signals": ["submit_too_fast", "session_flood"],
  "honeypot": null,
  "submitted_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
JSON
)"
    check_status "POST /hooks/problem-submitted (bot)" "200"
}

cmd_submit_honeypot() {
    header "Hook: problem-submitted  (Honeypot → sofortiger Reject)"
    sep
    info "Honeypot-Feld gesetzt → sofortiger Reject ohne LLM"
    do_request POST /hooks/problem-submitted "$(cat <<JSON
{
  "problem_id": "${PROBLEM_ID}-hp",
  "title": "Test problem",
  "description": "This should be rejected immediately",
  "ip_hash": "hp001",
  "signals": [],
  "honeypot": "http://spam.example.com",
  "submitted_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
JSON
)"
    check_status "POST /hooks/problem-submitted (honeypot)" "200"
}

cmd_approve() {
    header "Hook: problem-approved  (ID: ${PROBLEM_ID})"
    sep
    info "Startet Hintergrundpipeline: Embedding → AI-Lösung → Clustering → WS-Broadcast"
    info "Antwort ist sofortig, Pipeline läuft async"
    do_request POST /hooks/problem-approved "{\"problem_id\": \"${PROBLEM_ID}\"}"
    check_status "POST /hooks/problem-approved" "200"
}

cmd_vote() {
    header "Hook: vote-changed  (ID: ${PROBLEM_ID})"
    sep
    info "vote_score wird aus DB gelesen wenn new_score nicht angegeben"
    do_request POST /hooks/vote-changed "$(cat <<JSON
{
  "entity_id": "${PROBLEM_ID}",
  "entity_type": "problem"
}
JSON
)"
    check_status "POST /hooks/vote-changed" "200"
}

cmd_cluster() {
    header "Clustering manuell triggern"
    sep
    info "HDBSCAN auf allen approved Problems mit Embeddings"
    do_request POST /clustering/run
    check_status "POST /clustering/run" "200"
}

cmd_ws() {
    header "WebSocket-Verbindung"
    sep
    require_cmd websocat "websocat nicht gefunden — brew install websocat"
    info "Verbinde mit ${BASE_URL}/ws — warte auf Events (Ctrl+C zum Beenden)"
    info "Öffne ein zweites Terminal und schicke einen Hook-Call ab"
    echo ""
    local ws_url
    ws_url="${BASE_URL/http:/ws:}"
    ws_url="${ws_url/https:/wss:}"
    websocat "${ws_url}/ws"
}

cmd_all() {
    header "Smoke Test — alle Endpunkte"
    sep
    cmd_health
    cmd_similarity
    cmd_submit
    cmd_submit_bot
    cmd_submit_honeypot
    cmd_approve
    cmd_vote
    cmd_cluster
    echo ""
    sep
    ok "Smoke Test abgeschlossen"
    info "WebSocket-Test: $(basename "$0") ws"
    info "Swagger UI:     ${BASE_URL}/docs"
    sep
    echo ""
}

# ─── Dispatch ────────────────────────────────────────────────────────────────

case "$COMMAND" in
    health)          cmd_health ;;
    similarity)      cmd_similarity ;;
    submit)          cmd_submit ;;
    submit-bot)      cmd_submit_bot ;;
    submit-honeypot) cmd_submit_honeypot ;;
    approve)         cmd_approve ;;
    vote)            cmd_vote ;;
    cluster)         cmd_cluster ;;
    ws)              cmd_ws ;;
    all)             cmd_all ;;
    *)
        echo -e "${RED}Unbekannter Befehl: ${COMMAND}${RESET}" >&2
        usage; exit 1 ;;
esac
