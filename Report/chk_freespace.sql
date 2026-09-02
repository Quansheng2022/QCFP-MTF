-- Check db fragmentation
SELECT
    ROUND(page_count * page_size / 1024.0 / 1024.0, 2) AS db_size_mb,
    ROUND(freelist_count * page_size / 1024.0 / 1024.0, 2) AS free_mb,
    ROUND((page_count - freelist_count) * page_size / 1024.0 / 1024.0, 2) AS used_mb,
    ROUND(freelist_count * 100.0 / page_count, 2) AS free_percent
FROM (
    SELECT
        (SELECT page_count FROM pragma_page_count) AS page_count,
        (SELECT freelist_count FROM pragma_freelist_count) AS freelist_count,
        (SELECT page_size FROM pragma_page_size) AS page_size
);

-- Release free space
-- if free_percent > 20: VACUUM