<?php
// Copy to digest-config.php and fill in your SMTP details (e.g. Brevo free tier).
return [
    'host' => 'smtp-relay.brevo.com',
    'port' => 587,
    'user' => 'YOUR_BREVO_LOGIN',
    'pass' => 'YOUR_SMTP_KEY',
    'from' => 'newsletter@lusakabrief.com',
    'from_name' => 'Lusaka Brief',
];
