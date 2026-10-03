<?php
/**
 * Lusaka Brief — Newsletter signup endpoint
 * POST email -> stores in subscribers.json, returns JSON.
 * Caddy must proxy /subscribe.php to php-fpm, OR this runs via cronless CGI.
 * On our stack Caddy serves static only, so we run this through a tiny
 * php -S backend on 127.0.0.1:8077 (see deploy notes) proxied at /api/subscribe.
 */
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$STORE = '/var/lib/lusakabrief/subscribers.json';

$email = strtolower(trim($_POST['email'] ?? ''));
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Please enter a valid email address.']);
    exit;
}

$list = file_exists($STORE) ? (json_decode(file_get_contents($STORE), true) ?: []) : [];
foreach ($list as $s) {
    if ($s['email'] === $email) {
        echo json_encode(['ok' => true, 'message' => 'You are already on the list — welcome back.']);
        exit;
    }
}
$list[] = ['email' => $email, 'since' => date('c'), 'confirmed' => true];
file_put_contents($STORE, json_encode($list, JSON_PRETTY_PRINT));
echo json_encode(['ok' => true, 'message' => 'Welcome aboard — the next edition lands in your inbox at noon.']);
