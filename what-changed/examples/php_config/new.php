<?php
// Database configuration for the orders service
return [
    'default' => 'mysql',
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => 3306,
    'database' => 'orders',
    'charset' => 'utf8mb4',
    'timeout' => 60,
    'pool_size' => 10,
    'max_retries' => 3,
    'debug' => true,
    'strict' => true,
    'ssl_mode' => 'prefer',
    'log_queries' => false,
    'read_replica' => env('DB_REPLICA_HOST'),
];
