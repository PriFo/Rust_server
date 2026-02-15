-- ===================================================
-- MySQL Database Schema for BattleMetrics Bot
-- Версия 5.1 - Оптимизация для больших объемов данных
-- Изменения для совместимости:
-- 1. Убрано партиционирование по функциям (несовместимо с многими версиями)
-- 2. Убраны невидимые индексы INVISIBLE
-- 3. Упрощен синтаксис для максимальной совместимости
-- ===================================================

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema bm_db
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `bm_db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `bm_db`;

-- -----------------------------------------------------
-- Table `bm_db`.`games`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`games` (
  `id_game` TINYINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID игры',
  `game_name` VARCHAR(20) NOT NULL COMMENT 'Название игры (rust, arma3 и т.д.)',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_game`),
  UNIQUE INDEX `idx_game_name` (`game_name` ASC),
  INDEX `idx_games_created` (`created_at` DESC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Список поддерживаемых игр';

-- -----------------------------------------------------
-- Table `bm_db`.`servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`servers` (
  `id_server` BIGINT UNSIGNED NOT NULL COMMENT 'ID сервера на BattleMetrics',
  `fk_games_id` TINYINT UNSIGNED NOT NULL COMMENT 'ID игры',
  `server_name` VARCHAR(150) NOT NULL COMMENT 'Название сервера',
  `rank` MEDIUMINT UNSIGNED NULL DEFAULT NULL COMMENT 'Рейтинг сервера',
  `private` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг приватного сервера',
  `country` CHAR(2) NULL DEFAULT NULL COMMENT 'Код страны сервера (ISO 3166-1 alpha-2)',
  `ip` VARCHAR(45) NULL DEFAULT NULL COMMENT 'IP адрес сервера',
  `port` SMALLINT UNSIGNED NULL DEFAULT NULL COMMENT 'Порт сервера',
  `players_online` SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Игроков онлайн',
  `players_max` SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Максимум игроков',
  `status` ENUM('online', 'offline', 'unknown') NOT NULL DEFAULT 'unknown',
  `last_updated` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_server`),
  INDEX `idx_server_game` (`fk_games_id` ASC, `id_server` ASC),
  INDEX `idx_server_name` (`server_name`(50) ASC),
  INDEX `idx_server_country` (`country` ASC),
  INDEX `idx_server_players` (`players_online` DESC),
  INDEX `idx_server_updated` (`last_updated` DESC),
  CONSTRAINT `fk_servers_games1`
    FOREIGN KEY (`fk_games_id`)
    REFERENCES `bm_db`.`games` (`id_game`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Основная информация о серверах';

-- -----------------------------------------------------
-- Table `bm_db`.`servers_history`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`servers_history` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `id_server` BIGINT UNSIGNED NOT NULL COMMENT 'ID сервера на BattleMetrics',
  `players_online` SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Игроков онлайн',
  `players_max` SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Максимум игроков',
  `status` ENUM('online', 'offline', 'unknown') NOT NULL DEFAULT 'unknown',
  `recorded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_history_server_time` (`id_server` ASC, `recorded_at` DESC),
  INDEX `idx_history_time` (`recorded_at` DESC),
  CONSTRAINT `fk_servers_history_server`
    FOREIGN KEY (`id_server`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'История изменений серверов (для аналитики)';

-- -----------------------------------------------------
-- Table `bm_db`.`rust_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_servers` (
  `fk_id_servers` BIGINT UNSIGNED NOT NULL COMMENT 'ID сервера',
  `is_pve` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг PVE сервера',
  `official` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг официального сервера',
  `description` TEXT NULL DEFAULT NULL COMMENT 'Описание сервера',
  `modded` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг модифицированного сервера',
  `gamemode` VARCHAR(30) NULL DEFAULT NULL COMMENT 'Режим игры',
  `steam_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'Steam ID сервера',
  `next_wipe_date` DATETIME NULL DEFAULT NULL COMMENT 'Дата следующего вайпа',
  `next_wipe_type` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Тип следующего вайпа',
  `last_wipe_date` DATETIME NULL DEFAULT NULL COMMENT 'Дата последнего вайпа',
  `rust_url` VARCHAR(2000) NULL DEFAULT NULL COMMENT 'URL Rust сервера',
  `map_url` VARCHAR(2000) NULL DEFAULT NULL COMMENT 'URL карты',
  `thumbnail_url` VARCHAR(2000) NULL DEFAULT NULL COMMENT 'URL превью карты',
  `queued_players` SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Игроков в очереди',
  `last_updated` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`fk_id_servers`),
  INDEX `idx_rust_next_wipe` (`next_wipe_date` DESC),
  INDEX `idx_rust_last_wipe` (`last_wipe_date` DESC),
  INDEX `idx_rust_official` (`official` ASC),
  INDEX `idx_rust_queued` (`queued_players` DESC),
  INDEX `idx_rust_updated` (`last_updated` DESC),
  CONSTRAINT `fk_rust_servers_servers1`
    FOREIGN KEY (`fk_id_servers`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Дополнительная информация о Rust серверах';

-- -----------------------------------------------------
-- Table `bm_db`.`players`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players` (
  `id_players` BIGINT UNSIGNED NOT NULL COMMENT 'ID игрока на BattleMetrics',
  `nickname` VARCHAR(80) NOT NULL COMMENT 'Никнейм игрока',
  `positive_match` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг прямого совпадения данных',
  `private` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг приватного профиля',
  `last_seen` TIMESTAMP NULL DEFAULT NULL COMMENT 'Когда последний раз видели онлайн',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_players`),
  INDEX `idx_player_nickname` (`nickname`(40) ASC),
  INDEX `idx_player_updated` (`updated_at` DESC),
  INDEX `idx_player_last_seen` (`last_seen` DESC),
  INDEX `idx_player_private` (`private` ASC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Информация об игроках';

-- -----------------------------------------------------
-- Table `bm_db`.`players_history`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players_history` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `id_player` BIGINT UNSIGNED NOT NULL COMMENT 'ID игрока',
  `nickname` VARCHAR(80) NOT NULL COMMENT 'Никнейм игрока на момент записи',
  `server_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'ID сервера, где был игрок',
  `is_online` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Был ли онлайн',
  `recorded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_player_history_time` (`id_player` ASC, `recorded_at` DESC),
  INDEX `idx_player_history_server` (`server_id` ASC, `recorded_at` DESC),
  INDEX `idx_player_history_online` (`is_online` ASC, `recorded_at` DESC),
  CONSTRAINT `fk_players_history_player`
    FOREIGN KEY (`id_player`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_players_history_server`
    FOREIGN KEY (`server_id`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'История игроков (онлайн/офлайн, смена ника)';

-- -----------------------------------------------------
-- Table `bm_db`.`players_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players_servers` (
  `fk_id_server` BIGINT UNSIGNED NOT NULL COMMENT 'ID сервера',
  `fk_id_players` BIGINT UNSIGNED NOT NULL COMMENT 'ID игрока',
  `is_online` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг онлайн статуса',
  `time_played` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Время игры в секундах',
  `first_seen` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Когда впервые увидели на сервере',
  `last_seen` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Когда последний раз видели на сервере',
  PRIMARY KEY (`fk_id_server`, `fk_id_players`),
  INDEX `idx_player_server_online` (`fk_id_players` ASC, `is_online` DESC, `last_seen` DESC),
  INDEX `idx_server_player_online` (`fk_id_server` ASC, `is_online` DESC, `last_seen` DESC),
  INDEX `idx_player_last_seen` (`fk_id_players` ASC, `last_seen` DESC),
  INDEX `idx_server_last_seen` (`fk_id_server` ASC, `last_seen` DESC),
  CONSTRAINT `fk_players_servers_servers1`
    FOREIGN KEY (`fk_id_server`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_players_servers_players1`
    FOREIGN KEY (`fk_id_players`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Связь игроков с серверами (many-to-many)';

-- -----------------------------------------------------
-- Table `bm_db`.`profiles`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`profiles` (
  `id_profile` BIGINT UNSIGNED NOT NULL COMMENT 'ID пользователя Telegram',
  `profile_nickname` VARCHAR(80) NULL DEFAULT NULL COMMENT 'Никнейм пользователя в Telegram',
  `profile_name` VARCHAR(80) NULL DEFAULT NULL COMMENT 'Имя пользователя в Telegram',
  `profile_surname` VARCHAR(80) NULL DEFAULT NULL COMMENT 'Фамилия пользователя в Telegram',
  `bot_banned` BOOLEAN NULL DEFAULT FALSE COMMENT 'Флаг блокировки пользователя ботом',
  `is_active` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Флаг активности профиля',
  `notification_settings` JSON NULL DEFAULT NULL COMMENT 'Настройки уведомлений в JSON',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_activity` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_profile`),
  INDEX `idx_profile_active` (`is_active` ASC, `last_activity` DESC),
  INDEX `idx_profile_activity` (`last_activity` DESC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Профили пользователей Telegram бота';

-- -----------------------------------------------------
-- Table `bm_db`.`subscriptions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`subscriptions` (
  `id_subscription` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID подписки',
  `fk_id_profile` BIGINT UNSIGNED NOT NULL COMMENT 'ID профиля пользователя',
  `entity_type` ENUM('server', 'player') NOT NULL COMMENT 'Тип отслеживаемой сущности',
  `entity_id` BIGINT UNSIGNED NOT NULL COMMENT 'ID сервера или игрока',
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Подписка активна',
  `notification_types` JSON NULL DEFAULT NULL COMMENT 'Типы уведомлений в JSON',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_subscription`),
  UNIQUE INDEX `idx_profile_entity` (`fk_id_profile` ASC, `entity_type` ASC, `entity_id` ASC),
  INDEX `idx_subscription_entity` (`entity_type` ASC, `entity_id` ASC),
  INDEX `idx_subscription_active` (`is_active` ASC, `entity_type` ASC),
  INDEX `idx_subscription_updated` (`updated_at` DESC),
  CONSTRAINT `fk_subscriptions_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Подписки пользователей на серверы/игроков';

-- -----------------------------------------------------
-- Table `bm_db`.`server_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`server_filters` (
  `id_filter` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID фильтра сервера',
  `fk_id_profile` BIGINT UNSIGNED NOT NULL COMMENT 'ID профиля пользователя',
  `player_count_min` INT NULL DEFAULT NULL COMMENT 'Минимальное количество игроков (NULL = отключено)',
  `player_count_max` INT NULL DEFAULT NULL COMMENT 'Максимальное количество игроков (NULL = отключено)',
  `check_status` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения статуса',
  `check_ip_port` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения IP/порта',
  `check_private` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения приватности',
  `apply_to_all` BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Применять ко всем серверам пользователя',
  `specific_server_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'Если не apply_to_all - ID конкретного сервера',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_filter`),
  UNIQUE INDEX `idx_profile_server_filter` (`fk_id_profile` ASC, `specific_server_id` ASC),
  INDEX `fk_server_filter_profiles1_idx` (`fk_id_profile` ASC),
  INDEX `idx_filter_server` (`specific_server_id` ASC),
  CONSTRAINT `fk_server_filter_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_server_filter_server`
    FOREIGN KEY (`specific_server_id`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Фильтры для серверов';

-- -----------------------------------------------------
-- Table `bm_db`.`rust_servers_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_servers_filters` (
  `id_filter` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID Rust фильтра',
  `fk_server_filters_id` INT UNSIGNED NOT NULL COMMENT 'ID связанного server_filter',
  `queued_players_min` INT NULL DEFAULT NULL COMMENT 'Минимальное количество игроков в очереди (NULL = отключено)',
  `check_last_wipe` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения последнего вайпа',
  `check_next_wipe` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения следующего вайпа',
  `check_pve` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения PVE статуса',
  `check_url` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения URL сервера',
  `check_map_url` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения URL карты',
  `check_map_image` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Проверка изменения изображения карты',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_filter`),
  INDEX `fk_rust_servers_filters_server_filter1_idx` (`fk_server_filters_id` ASC),
  CONSTRAINT `fk_rust_servers_filters_server_filter1`
    FOREIGN KEY (`fk_server_filters_id`)
    REFERENCES `bm_db`.`server_filters` (`id_filter`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Дополнительные фильтры для Rust серверов';

-- -----------------------------------------------------
-- Table `bm_db`.`player_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`player_filters` (
  `id_player_filter` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID фильтра игрока',
  `fk_id_profile` BIGINT UNSIGNED NOT NULL COMMENT 'ID профиля пользователя',
  `player_name_changed` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения имени игрока',
  `player_private_changed` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения приватности профиля',
  `check_online_status` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения онлайн статуса',
  `check_server_change` BOOLEAN NULL DEFAULT FALSE COMMENT 'Проверка изменения сервера',
  `apply_to_all` BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Применять ко всем игрокам пользователя',
  `specific_player_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'Если не apply_to_all - ID конкретного игрока',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_player_filter`),
  UNIQUE INDEX `idx_profile_player_filter` (`fk_id_profile` ASC, `specific_player_id` ASC),
  INDEX `fk_player_filters_profiles1_idx` (`fk_id_profile` ASC),
  INDEX `idx_filter_player` (`specific_player_id` ASC),
  CONSTRAINT `fk_player_filters_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_player_filters_player`
    FOREIGN KEY (`specific_player_id`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Фильтры для игроков';

-- -----------------------------------------------------
-- Table `bm_db`.`logs`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`logs` (
  `id_log` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID лога',
  `fk_id_profile` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'ID профиля пользователя',
  `log_type` ENUM('user_message', 'bot_response', 'system', 'api_call', 'error') NOT NULL DEFAULT 'system',
  `message_text` TEXT NULL DEFAULT NULL COMMENT 'Текст сообщения/ошибки',
  `error_details` TEXT NULL DEFAULT NULL COMMENT 'Детали ошибки (stack trace)',
  `log_date` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_log`),
  INDEX `idx_log_profile_date` (`fk_id_profile` ASC, `log_date` DESC),
  INDEX `idx_log_type_date` (`log_type` ASC, `log_date` DESC),
  INDEX `idx_log_date` (`log_date` DESC),
  CONSTRAINT `fk_logs_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Логи системы';

-- -----------------------------------------------------
-- Table `bm_db`.`suggestions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`suggestions` (
  `id_suggestions` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID предложения',
  `fk_id_profile` BIGINT UNSIGNED NOT NULL COMMENT 'ID профиля пользователя',
  `msg_txt` TEXT NOT NULL COMMENT 'Текст предложения/отчета',
  `is_answered` BOOLEAN NULL DEFAULT FALSE COMMENT 'Флаг ответа на предложение',
  `is_accepted` BOOLEAN NULL DEFAULT FALSE COMMENT 'Флаг принятия предложения',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `answered_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата ответа',
  `accepted_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата подтверждения',
  PRIMARY KEY (`id_suggestions`),
  INDEX `fk_suggestions_profiles1_idx` (`fk_id_profile` ASC),
  INDEX `idx_suggestion_status` (`is_answered` ASC, `is_accepted` ASC),
  INDEX `idx_suggestion_created` (`created_at` DESC),
  CONSTRAINT `fk_suggestions_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Предложения и отчеты пользователей';

-- -----------------------------------------------------
-- Table `bm_db`.`cache`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`cache` (
  `cache_key` VARCHAR(255) NOT NULL COMMENT 'Ключ кэша',
  `cache_value` LONGTEXT NOT NULL COMMENT 'Значение кэша',
  `expires_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Время истечения кэша',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`cache_key`),
  INDEX `idx_cache_expires` (`expires_at` ASC),
  INDEX `idx_cache_updated` (`updated_at` DESC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Кэш для ускорения запросов (API ответы и т.д.)';

-- -----------------------------------------------------
-- Table `bm_db`.`maintenance_log`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`maintenance_log` (
  `id_maintenance` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `operation_type` ENUM('backup', 'optimize', 'repair', 'migration') NOT NULL,
  `table_name` VARCHAR(64) NULL DEFAULT NULL,
  `records_affected` INT UNSIGNED NULL DEFAULT NULL,
  `duration_ms` INT UNSIGNED NOT NULL,
  `status` ENUM('success', 'warning', 'error') NOT NULL,
  `details` TEXT NULL DEFAULT NULL,
  `performed_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_maintenance`),
  INDEX `idx_maintenance_time` (`performed_at` DESC),
  INDEX `idx_maintenance_type` (`operation_type` ASC, `performed_at` DESC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Лог обслуживания БД';

-- -----------------------------------------------------
-- Table `bm_db`.`initialization_state`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`initialization_state` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'ID записи состояния',
  `admin_id` BIGINT UNSIGNED NOT NULL COMMENT 'ID администратора',
  `error_type` VARCHAR(50) NOT NULL COMMENT 'Тип ошибки (servers_loading, players_loading)',
  `error_url` TEXT NULL DEFAULT NULL COMMENT 'URL страницы, на которой произошла ошибка',
  `error_message` TEXT NULL DEFAULT NULL COMMENT 'Сообщение об ошибке',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Время создания записи',
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Время обновления записи',
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_admin_error_type` (`admin_id` ASC, `error_type` ASC),
  INDEX `idx_init_state_admin` (`admin_id` ASC),
  INDEX `idx_init_state_type` (`error_type` ASC),
  INDEX `idx_init_state_created` (`created_at` DESC)
) ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
ROW_FORMAT = COMPRESSED
KEY_BLOCK_SIZE = 8
COMMENT = 'Состояние инициализации БД для возобновления после ошибок';

-- -----------------------------------------------------
-- Вставка начальных данных
-- -----------------------------------------------------

-- Вставка игры Rust
INSERT IGNORE INTO `bm_db`.`games` (`id_game`, `game_name`) VALUES (1, 'rust');

-- Вставка других популярных игр
INSERT IGNORE INTO `bm_db`.`games` (`id_game`, `game_name`) VALUES 
(2, 'arma3'),
(3, 'dayz'),
(4, 'minecraft'),
(5, '7daystodie'),
(6, 'valheim'),
(7, 'ark'),
(8, 'conanexiles'),
(9, 'teamfortress2'),
(10, 'counterstrike2');

-- -----------------------------------------------------
-- Восстановление настроек SQL
-- -----------------------------------------------------

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;