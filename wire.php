<?php
/**
 * Lusaka Brief — Wire Service
 * Pulls Zambian news RSS feeds, dedupes, and writes wire.json.
 * Run via Hostinger cron, e.g. every 2 hours:
 *   php /home/YOURUSER/public_html/wire.php
 * No output needed on the page: the site's JS reads /wire.json.
 */

$FEEDS = [
    'Lusaka Times'   => 'https://www.lusakatimes.com/feed/',
    'News Diggers'   => 'https://diggers.news/feed/',
    'Times of Zambia'=> 'https://www.times.co.zm/feed/',
    'ZNBC'           => 'https://znbc.co.zm/feed/',
];

$MAX_ITEMS   = 60;    // keep the newest 60 wire items
$ARCHIVE_DAYS= 30;    // drop items older than 30 days
$OUT         = __DIR__ . '/wire.json';

// ---------- load existing ----------
$existing = [];
if (file_exists($OUT)) {
    $j = json_decode(file_get_contents($OUT), true);
    if (isset($j['items'])) $existing = $j['items'];
}
$seen = [];
foreach ($existing as $it) $seen[$it['url']] = true;

// ---------- fetch feeds ----------
function fetch_feed($url) {
    $ctx = stream_context_create(['http' => [
        'timeout' => 15,
        'user_agent' => 'LusakaBriefWire/1.0 (+https://lusakabrief.com)',
    ]]);
    $raw = @file_get_contents($url, false, $ctx);
    if (!$raw) return null;
    libxml_use_internal_errors(true);
    $xml = simplexml_load_string($raw);
    return $xml ?: null;
}

$new = [];
foreach ($FEEDS as $source => $feedUrl) {
    $xml = fetch_feed($feedUrl);
    if (!$xml) continue;

    // RSS 2.0
    if (isset($xml->channel->item)) {
        foreach ($xml->channel->item as $item) {
            $link = trim((string)$item->link);
            if (!$link || isset($seen[$link])) continue;
            $new[] = [
                'source' => $source,
                'title'  => trim((string)$item->title),
                'url'    => $link,
                'excerpt'=> mb_substr(trim(strip_tags((string)$item->description)), 0, 220),
                'iso'    => date('c', strtotime((string)$item->pubDate) ?: time()),
            ];
        }
    }
    // Atom
    elseif (isset($xml->entry)) {
        foreach ($xml->entry as $entry) {
            $link = '';
            foreach ($entry->link as $l) {
                if ((string)$l['rel'] === 'alternate' || !$link) $link = trim((string)$l['href']);
            }
            if (!$link || isset($seen[$link])) continue;
            $summary = (string)($entry->summary ?? $entry->content ?? '');
            $new[] = [
                'source' => $source,
                'title'  => trim((string)$entry->title),
                'url'    => $link,
                'excerpt'=> mb_substr(trim(strip_tags($summary)), 0, 220),
                'iso'    => date('c', strtotime((string)($entry->published ?? $entry->updated)) ?: time()),
            ];
        }
    }
}

// ---------- merge, trim, save ----------
$all = array_merge($new, $existing);
usort($all, fn($a, $b) => strcmp($b['iso'], $a['iso']));
$cutoff = date('c', strtotime("-{$ARCHIVE_DAYS} days"));
$all = array_values(array_filter($all, fn($i) => $i['iso'] >= $cutoff));
$all = array_slice($all, 0, $MAX_ITEMS);

file_put_contents($OUT, json_encode([
    'updated'  => date('c'),
    'count'    => count($all),
    'items'    => $all,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

echo 'Wire updated: ' . count($new) . " new, " . count($all) . " total\n";
