<?php
/**
 * Lusaka Brief — Daily digest sender (cron, ~12:30 CAT after the edition lands)
 * Reads newest stories from assets/stories.json and emails subscribers.
 * Configure SMTP in digest-config.php (copy from digest-config.sample.php).
 * Without config it does nothing — safe to cron.
 */
$CFG = __DIR__ . '/digest-config.php';
if (!file_exists($CFG)) { echo "no config, skipping\n"; exit; }
$c = require $CFG;  // ['host'=>,'port'=>587,'user'=>,'pass'=>,'from'=>'newsletter@lusakabrief.com','from_name'=>'Lusaka Brief']

$SUBS = '/var/lib/lusakabrief/subscribers.json';
if (!file_exists($SUBS)) { echo "no subscribers\n"; exit; }
$subs = json_decode(file_get_contents($SUBS), true) ?: [];
if (!$subs) { echo "no subscribers\n"; exit; }

$stories = json_decode(file_get_contents(__DIR__ . '/../assets/stories.json'), true);
$today = date('Y-m-d');
$fresh = array_values(array_filter($stories, fn($s) => $s['iso'] === $today));
if (!$fresh) { echo "no fresh stories today\n"; exit; }
usort($fresh, fn($a, $b) => strcmp($b['iso'], $a['iso']));

$dateStr = date('l, j F Y');
$items = '';
foreach (array_slice($fresh, 0, 8) as $s) {
    $href = 'https://lusakabrief.com/news/' . $s['slug'] . '/';
    $items .= '<tr><td style="padding:18px 0;border-bottom:1px solid #e6e0d0">'
        . '<div style="font:700 11px Inter,Arial;letter-spacing:.12em;text-transform:uppercase;color:#b4551f">' . htmlspecialchars($s['tag']) . '</div>'
        . '<a href="' . $href . '" style="font:600 20px Georgia,serif;color:#173f2f;text-decoration:none;line-height:1.3">' . htmlspecialchars($s['title']) . '</a>'
        . '<p style="font:14px Inter,Arial;color:#55503f;line-height:1.55;margin:6px 0 0">' . htmlspecialchars($s['excerpt']) . '</p></td></tr>';
}
$html = '<!DOCTYPE html><html><body style="margin:0;background:#f7f4ec;padding:24px">'
    . '<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e6e0d0;padding:32px">'
    . '<div style="text-align:center;border-bottom:3px double #173f2f;padding-bottom:16px">'
    . '<div style="font:900 28px Georgia,serif;color:#173f2f">LUSAKA <span style="color:#b4551f">BRIEF</span></div>'
    . '<div style="font:12px Inter,Arial;color:#8a8474;letter-spacing:.15em;text-transform:uppercase;margin-top:4px">Daily Edition · ' . $dateStr . '</div></div>'
    . '<table width="100%" cellpadding="0" cellspacing="0">' . $items . '</table>'
    . '<p style="font:12px Inter,Arial;color:#8a8474;text-align:center;margin-top:24px">You are receiving the Lusaka Brief daily edition.<br><a href="https://lusakabrief.com" style="color:#b4551f">lusakabrief.com</a></p>'
    . '</div></body></html>';

// --- minimal SMTP client (STARTTLS) ---
function smtp_send($c, $to, $subject, $html) {
    $fp = stream_socket_client("tcp://{$c['host']}:{$c['port']}", $en, $es, 20);
    if (!$fp) return false;
    $rd = fn() => fgets($fp, 515);
    $cmd = function($l) use ($fp, $rd) { fwrite($fp, $l . "\r\n"); return $rd(); };
    $rd(); $cmd("EHLO lusakabrief.com");
    for ($i=0;$i<4;$i++) $rd();
    $cmd("STARTTLS");
    stream_socket_enable_crypto($fp, true, STREAM_CRYPTO_METHOD_TLS_CLIENT);
    $cmd("EHLO lusakabrief.com"); for ($i=0;$i<4;$i++) $rd();
    $cmd("AUTH LOGIN"); $cmd(base64_encode($c['user'])); $cmd(base64_encode($c['pass']));
    $cmd("MAIL FROM:<{$c['from']}>");
    $cmd("RCPT TO:<$to>");
    $cmd("DATA");
    $msg = "From: {$c['from_name']} <{$c['from']}>\r\nTo: <$to>\r\nSubject: $subject\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n$html\r\n.";
    $cmd($msg);
    $cmd("QUIT"); fclose($fp);
    return true;
}

$sent = 0;
foreach ($subs as $s) {
    if (smtp_send($c, $s['email'], "Lusaka Brief — $dateStr", $html)) $sent++;
}
echo "digest sent to $sent/" . count($subs) . "\n";
