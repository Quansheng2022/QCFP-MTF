-- Check table size.
SELECT
    name,
    SUM(pgsize) AS bytes
FROM dbstat
WHERE name LIKE 'hk_%'
GROUP BY name
ORDER BY bytes DESC;

