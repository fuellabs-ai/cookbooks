<?php
// Database settings for the orders service
return [
    'default' => 'mysql',
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => 3306,
    'database' => 'orders',
    'charset' => 'utf8mb4',
    'timeout' => 30,
    'pool_size' => 10,
    'retry_attempts' => 3,
    'debug' => false,
    'strict' => true,
    'ssl_mode' => 'require',
    'log_queries' => false,
];
