-- MariaDB example. DATETIME(3) stores KST wall-clock values without a timezone offset.

CREATE TABLE `dim_member` (
  `member_key` VARCHAR(128) NOT NULL,
  `member_no` VARCHAR(128) NULL,
  `birth_date` DATE NULL,
  `join_date` DATE NULL,
  `source_row_id` TEXT NULL,
  PRIMARY KEY (`member_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `dim_horse` (
  `horse_key` VARCHAR(128) NOT NULL,
  `horse_name` TEXT NULL,
  `birth_date` DATE NULL,
  `sire_name` TEXT NULL,
  `dam_name` TEXT NULL,
  `identity_status` TEXT NULL,
  PRIMARY KEY (`horse_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `dim_race` (
  `race_id` VARCHAR(128) NOT NULL,
  `race_date` DATE NULL,
  `race_no` INT NULL,
  `meet_cd` TEXT NULL,
  `race_start_at` DATETIME(3) NULL,
  `distance_m` INT NULL,
  `race_grade` TEXT NULL,
  `source_row_id` TEXT NULL,
  PRIMARY KEY (`race_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `dim_date` (
  `date_key` INT NOT NULL,
  `calendar_date` DATE NULL,
  `year` INT NULL,
  `quarter` INT NULL,
  `month` INT NULL,
  `day_of_month` INT NULL,
  `weekday` INT NULL,
  `year_month` TEXT NULL,
  PRIMARY KEY (`date_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `dim_channel` (
  `channel_key` VARCHAR(128) NOT NULL,
  `channel_cd` VARCHAR(128) NULL,
  `channel_group` TEXT NULL,
  `branch_no` TEXT NULL,
  `channel_name` TEXT NULL,
  PRIMARY KEY (`channel_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fct_bet_selection_cancel_50s` (
  `fact_id` VARCHAR(128) NOT NULL,
  `original_order_no` VARCHAR(128) NULL,
  `member_key` VARCHAR(128) NULL,
  `horse_key` VARCHAR(128) NULL,
  `race_id` VARCHAR(128) NULL,
  `channel_key` VARCHAR(128) NULL,
  `purchase_date_key` INT NULL,
  `cancel_date_key` INT NULL,
  `race_date_key` INT NULL,
  `snapshot_date_key` INT NULL,
  `bet_type_cd` VARCHAR(128) NULL,
  `chul_no` INT NULL,
  `age_at_purchase` INT NULL,
  `purchase_at` DATETIME(3) NULL,
  `horse_age_at_race` INT NULL,
  `horse_sex_at_race` TEXT NULL,
  `purchase_detail_count` BIGINT NULL,
  `purchase_stake_units` BIGINT NULL,
  `purchase_amount_krw` BIGINT NULL,
  `horse_snapshot_date` DATE NULL,
  `snapshot_age_days` INT NULL,
  `recent1y_starts` BIGINT NULL,
  `recent1y_wins` BIGINT NULL,
  `recent1y_win_rate` DOUBLE NULL,
  `recent1y_win_rate_band` TEXT NULL,
  `career_starts` BIGINT NULL,
  `career_wins` BIGINT NULL,
  `career_win_rate` DOUBLE NULL,
  `has_verified_customer_cancel` INT NULL,
  `cancel_label_status` TEXT NULL,
  `cancel_transaction_count` BIGINT NULL,
  `raw_linked_cancel_amount_krw` BIGINT NULL,
  `verified_cancel_amount_krw` BIGINT NULL,
  `verified_cancel_stake_units` BIGINT NULL,
  `first_cancel_at` DATETIME(3) NULL,
  `cancel_delay_seconds` BIGINT NULL,
  `late_cancel_detail_count` BIGINT NULL,
  `unresolved_cancel_order_count` BIGINT NULL,
  `header_detail_mismatch` INT NULL,
  `observation_end_at` DATETIME(3) NULL,
  `analysis_eligible` INT NULL,
  `exclusion_reasons` TEXT NULL,
  `purchase_order_row_id` TEXT NULL,
  `entry_row_id` TEXT NULL,
  `snapshot_row_id` TEXT NULL,
  `dq_dataset_version` TEXT NULL,
  `rule_version` TEXT NULL,
  PRIMARY KEY (`fact_id`),
  UNIQUE KEY uq_selection (`original_order_no`,`race_id`,`bet_type_cd`,`chul_no`),
  FOREIGN KEY (`member_key`) REFERENCES `dim_member` (`member_key`),
  FOREIGN KEY (`horse_key`) REFERENCES `dim_horse` (`horse_key`),
  FOREIGN KEY (`race_id`) REFERENCES `dim_race` (`race_id`),
  FOREIGN KEY (`channel_key`) REFERENCES `dim_channel` (`channel_key`),
  FOREIGN KEY (`purchase_date_key`) REFERENCES `dim_date` (`date_key`),
  FOREIGN KEY (`cancel_date_key`) REFERENCES `dim_date` (`date_key`),
  FOREIGN KEY (`race_date_key`) REFERENCES `dim_date` (`date_key`),
  FOREIGN KEY (`snapshot_date_key`) REFERENCES `dim_date` (`date_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Always filter eligible purchases; cancellation orders are not denominator rows.
SELECT recent1y_win_rate_band, COUNT(*) AS purchase_groups,
       SUM(has_verified_customer_cancel) AS cancelled_groups,
       SUM(has_verified_customer_cancel) / NULLIF(COUNT(*),0) AS cancel_rate,
       SUM(verified_cancel_amount_krw) / NULLIF(SUM(purchase_amount_krw),0) AS amount_cancel_rate
FROM fct_bet_selection_cancel_50s WHERE analysis_eligible=1 GROUP BY recent1y_win_rate_band;
