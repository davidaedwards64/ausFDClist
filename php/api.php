<?php
/**
 * Australian FDC Database — JSON API
 * Deploy to: davidaedwards.com/ausfdclist/api.php
 *
 * Actions (via POST JSON body or ?action= GET param):
 *   search_covers     — search Covers LEFT JOIN Issues
 *   search_issues     — search Issues table
 *   cover_details     — single cover + parent issue
 *   issue_with_covers — issue + all child covers
 *   statistics        — aggregate counts
 *
 * Credentials (db_user, db_pass) must be supplied in the POST JSON body.
 * They are NOT stored in this file; they are obtained at runtime via
 * Okta STS vaulted-secret token exchange in the FastAPI backend.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// ── Parse request body ──────────────────────────────────────────────────────
$data = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $raw = file_get_contents('php://input');
    if ($raw !== '') {
        $decoded = json_decode($raw, true);
        if (json_last_error() === JSON_ERROR_NONE && is_array($decoded)) {
            $data = $decoded;
        }
    }
}

// ── Database connection ────────────────────────────────────────────────────
define('DB_HOST',    'localhost');
define('DB_NAME',    'ausfdc');
define('DB_CHARSET', 'utf8mb4');

// Credentials come from the POST body (supplied by FastAPI after STS exchange).
$db_user = $data['db_user'] ?? null;
$db_pass = $data['db_pass'] ?? null;

// Validate credentials are present for DB-accessing actions
$action = $data['action'] ?? $_GET['action'] ?? '';
$no_db_actions = [];   // all actions require DB access

if (!in_array($action, $no_db_actions, true)) {
    if ($db_user === null || $db_user === '' || $db_pass === null) {
        json_response(['error' => "db_user and db_pass are required. Credentials must be supplied via the POST JSON body."], 400);
    }
}

function get_db(string $db_user, string $db_pass): PDO {
    $dsn = 'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=' . DB_CHARSET;
    $options = [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ];
    return new PDO($dsn, $db_user, $db_pass, $options);
}

// ── Helper ─────────────────────────────────────────────────────────────────
function json_response(array $data, int $status = 200): void {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function error_response(string $message, int $status = 400): void {
    json_response(['error' => $message], $status);
}

function intval_clamp(mixed $val, int $min, int $max, int $default): int {
    if ($val === null || $val === '') return $default;
    $n = (int) $val;
    return max($min, min($max, $n));
}

// ── Routing ────────────────────────────────────────────────────────────────
try {
    $pdo = get_db($db_user, $db_pass);

    switch ($action) {
        case 'search_covers':
            action_search_covers($pdo, $data);
            break;
        case 'search_issues':
            action_search_issues($pdo, $data);
            break;
        case 'cover_details':
            action_cover_details($pdo, $data);
            break;
        case 'issue_with_covers':
            action_issue_with_covers($pdo, $data);
            break;
        case 'statistics':
            action_statistics($pdo, $data);
            break;
        default:
            error_response("Unknown action: '$action'. Valid actions: search_covers, search_issues, cover_details, issue_with_covers, statistics.");
    }
} catch (PDOException $e) {
    error_response('Database error: ' . $e->getMessage(), 500);
}

// ── Actions ────────────────────────────────────────────────────────────────

function action_search_covers(PDO $pdo, array $data): void {
    $year   = $data['year']   ?? $_GET['year']   ?? null;
    $text   = $data['text']   ?? $_GET['text']   ?? null;
    $type   = $data['type']   ?? $_GET['type']   ?? null;
    $source = $data['source'] ?? $_GET['source'] ?? null;
    $limit  = intval_clamp($data['limit'] ?? $_GET['limit'] ?? null, 1, 100, 20);

    $where  = [];
    $params = [];

    if ($year !== null && $year !== '') {
        $where[]  = 'c.Date LIKE :year';
        $params[':year'] = $year . '%';
    }

    if ($text !== null && $text !== '') {
        $where[]  = '(c.Title LIKE :text1 OR c.AKA LIKE :text2 OR i.Title LIKE :text3 OR i.Series LIKE :text4)';
        $params[':text1'] = '%' . $text . '%';
        $params[':text2'] = '%' . $text . '%';
        $params[':text3'] = '%' . $text . '%';
        $params[':text4'] = '%' . $text . '%';
    }

    if ($type !== null && $type !== '') {
        $where[]  = 'c.Type LIKE :type';
        $params[':type'] = '%' . $type . '%';
    }

    if ($source !== null && $source !== '') {
        $where[]  = 'c.Source LIKE :source';
        $params[':source'] = '%' . $source . '%';
    }

    $whereClause = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    $sql = "
        SELECT
            c.Id,
            c.CoverId,
            c.Date,
            c.Title,
            c.AKA,
            c.Type,
            c.Description,
            c.Stamps,
            c.Pic1, c.Pic2, c.Pic3, c.Pic4,
            c.Size,
            c.Notes,
            c.Source,
            i.IssueId,
            i.Title      AS IssueTitle,
            i.Series     AS IssueSeries,
            i.StampPic
        FROM Covers c
        LEFT JOIN Issues i
            ON SUBSTRING_INDEX(c.CoverId, '-', 2) = i.IssueId
        $whereClause
        ORDER BY c.Date DESC, c.CoverId ASC
        LIMIT :limit
    ";

    $stmt = $pdo->prepare($sql);
    foreach ($params as $key => $val) {
        $stmt->bindValue($key, $val);
    }
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll();

    json_response([
        'action' => 'search_covers',
        'count'  => count($rows),
        'covers' => $rows,
    ]);
}


function action_search_issues(PDO $pdo, array $data): void {
    $year   = $data['year']   ?? $_GET['year']   ?? null;
    $text   = $data['text']   ?? $_GET['text']   ?? null;
    $series = $data['series'] ?? $_GET['series'] ?? null;
    $type   = $data['type']   ?? $_GET['type']   ?? null;
    $limit  = intval_clamp($data['limit'] ?? $_GET['limit'] ?? null, 1, 100, 20);

    $where  = [];
    $params = [];

    if ($year !== null && $year !== '') {
        $where[]  = 'Date LIKE :year';
        $params[':year'] = $year . '%';
    }

    if ($text !== null && $text !== '') {
        $where[]  = '(Title LIKE :text1 OR AKA LIKE :text2 OR Series LIKE :text3)';
        $params[':text1'] = '%' . $text . '%';
        $params[':text2'] = '%' . $text . '%';
        $params[':text3'] = '%' . $text . '%';
    }

    if ($series !== null && $series !== '') {
        $where[]  = 'Series LIKE :series';
        $params[':series'] = '%' . $series . '%';
    }

    if ($type !== null && $type !== '') {
        $where[]  = 'Type LIKE :type';
        $params[':type'] = '%' . $type . '%';
    }

    $whereClause = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    $sql = "
        SELECT
            Id,
            IssueId,
            Date,
            Title,
            AKA,
            Series,
            Type,
            Description,
            Stamps,
            SBNbr,
            Notes,
            StampPic
        FROM Issues
        $whereClause
        ORDER BY Date DESC, IssueId ASC
        LIMIT :limit
    ";

    $stmt = $pdo->prepare($sql);
    foreach ($params as $key => $val) {
        $stmt->bindValue($key, $val);
    }
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll();

    json_response([
        'action' => 'search_issues',
        'count'  => count($rows),
        'issues' => $rows,
    ]);
}


function action_cover_details(PDO $pdo, array $data): void {
    $id = $data['id'] ?? $_GET['id'] ?? null;

    if ($id === null || $id === '') {
        error_response("Parameter 'id' (CoverId) is required.");
    }

    $sql = "
        SELECT
            c.Id,
            c.CoverId,
            c.Date,
            c.Title,
            c.AKA,
            c.Type,
            c.Description,
            c.Stamps,
            c.Pic1, c.Pic2, c.Pic3, c.Pic4,
            c.Size,
            c.Notes,
            c.Source,
            i.IssueId,
            i.Date       AS IssueDate,
            i.Title      AS IssueTitle,
            i.AKA        AS IssueAKA,
            i.Series     AS IssueSeries,
            i.Type       AS IssueType,
            i.Description AS IssueDescription,
            i.Stamps     AS IssueStamps,
            i.SBNbr,
            i.Notes      AS IssueNotes,
            i.StampPic
        FROM Covers c
        LEFT JOIN Issues i
            ON SUBSTRING_INDEX(c.CoverId, '-', 2) = i.IssueId
        WHERE c.CoverId = :id
        LIMIT 1
    ";

    $stmt = $pdo->prepare($sql);
    $stmt->execute([':id' => $id]);
    $row = $stmt->fetch();

    if (!$row) {
        error_response("Cover not found: $id", 404);
    }

    json_response([
        'action' => 'cover_details',
        'cover'  => $row,
    ]);
}


function action_issue_with_covers(PDO $pdo, array $data): void {
    $issue_id = $data['issue_id'] ?? $_GET['issue_id'] ?? null;

    if ($issue_id === null || $issue_id === '') {
        error_response("Parameter 'issue_id' is required.");
    }

    $stmt = $pdo->prepare("
        SELECT Id, IssueId, Date, Title, AKA, Series, Type, Description,
               Stamps, SBNbr, Notes, StampPic
        FROM Issues
        WHERE IssueId = :issue_id
        LIMIT 1
    ");
    $stmt->execute([':issue_id' => $issue_id]);
    $issue = $stmt->fetch();

    if (!$issue) {
        error_response("Issue not found: $issue_id", 404);
    }

    $stmt2 = $pdo->prepare("
        SELECT Id, CoverId, Date, Title, AKA, Type, Description, Stamps,
               Pic1, Pic2, Pic3, Pic4, Size, Notes, Source
        FROM Covers
        WHERE SUBSTRING_INDEX(CoverId, '-', 2) = :issue_id
        ORDER BY CoverId ASC
    ");
    $stmt2->execute([':issue_id' => $issue_id]);
    $covers = $stmt2->fetchAll();

    json_response([
        'action'      => 'issue_with_covers',
        'issue'       => $issue,
        'cover_count' => count($covers),
        'covers'      => $covers,
    ]);
}


function action_statistics(PDO $pdo, array $data): void {
    $stat_type = $data['stat_type'] ?? $_GET['stat_type'] ?? null;
    $table     = $data['table']     ?? $_GET['table']     ?? 'covers';

    if ($stat_type === null || $stat_type === '') {
        error_response("Parameter 'stat_type' is required. Valid values: total, by_year, by_source, by_type.");
    }

    if (!in_array($table, ['covers', 'issues'], true)) {
        error_response("Invalid table. Must be 'covers' or 'issues'.");
    }

    $tbl = ($table === 'covers') ? 'Covers' : 'Issues';

    switch ($stat_type) {
        case 'total':
            $stmt = $pdo->query("SELECT COUNT(*) AS total FROM $tbl");
            $row  = $stmt->fetch();
            json_response([
                'action'    => 'statistics',
                'stat_type' => 'total',
                'table'     => $table,
                'total'     => (int) $row['total'],
            ]);
            break;

        case 'by_year':
            $stmt = $pdo->query("
                SELECT YEAR(Date) AS year, COUNT(*) AS count
                FROM $tbl
                WHERE Date IS NOT NULL
                GROUP BY YEAR(Date)
                ORDER BY year ASC
            ");
            json_response([
                'action'    => 'statistics',
                'stat_type' => 'by_year',
                'table'     => $table,
                'rows'      => $stmt->fetchAll(),
            ]);
            break;

        case 'by_source':
            if ($table !== 'covers') {
                error_response("by_source is only available for the 'covers' table.");
            }
            $stmt = $pdo->query("
                SELECT Source, COUNT(*) AS count
                FROM Covers
                GROUP BY Source
                ORDER BY count DESC
            ");
            json_response([
                'action'    => 'statistics',
                'stat_type' => 'by_source',
                'table'     => 'covers',
                'rows'      => $stmt->fetchAll(),
            ]);
            break;

        case 'by_type':
            $stmt = $pdo->query("
                SELECT Type, COUNT(*) AS count
                FROM $tbl
                GROUP BY Type
                ORDER BY count DESC
            ");
            json_response([
                'action'    => 'statistics',
                'stat_type' => 'by_type',
                'table'     => $table,
                'rows'      => $stmt->fetchAll(),
            ]);
            break;

        default:
            error_response("Invalid stat_type '$stat_type'. Valid values: total, by_year, by_source, by_type.");
    }
}
