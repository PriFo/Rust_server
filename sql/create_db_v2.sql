-- ===================================================
-- MySQL Database Schema for BattleMetrics Bot
-- Версия 2.0 - Обновлено с учетом всех изменений проекта
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
-- Table `bm_db`.`profiles`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`profiles` (
  `id_profile` VARCHAR(50) NOT NULL COMMENT 'ID пользователя Telegram (может быть строкой)',
  `profile_nickname` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Никнейм пользователя в Telegram',
  `profile_name` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Имя пользователя в Telegram',
  `profile_surname` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Фамилия пользователя в Telegram',
  `bot_banned` TINYINT(1) NULL DEFAULT 0 COMMENT 'Флаг блокировки пользователя ботом',
  `is_active` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг активности профиля (профиль активен после подтверждения пользователем после перезапуска бота)',
  PRIMARY KEY (`id_profile`),
  INDEX `idx_profile_nickname` (`profile_nickname` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Профили пользователей Telegram бота';

-- -----------------------------------------------------
-- Table `bm_db`.`games`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`games` (
  `id_game` INT NOT NULL AUTO_INCREMENT COMMENT 'ID игры',
  `game_name` VARCHAR(45) NOT NULL COMMENT 'Название игры (rust, arma3 и т.д.)',
  PRIMARY KEY (`id_game`),
  UNIQUE INDEX `idx_game_name` (`game_name` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Список поддерживаемых игр';

-- -----------------------------------------------------
-- Table `bm_db`.`servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`servers` (
  `id_server` VARCHAR(50) NOT NULL COMMENT 'ID сервера на BattleMetrics (может быть строкой)',
  `fk_games_id` INT NOT NULL COMMENT 'ID игры',
  `server_name` VARCHAR(200) NOT NULL COMMENT 'Название сервера',
  `rank` INT NULL DEFAULT NULL COMMENT 'Рейтинг сервера',
  `private` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг приватного сервера',
  `country` VARCHAR(10) NULL DEFAULT NULL COMMENT 'Код страны сервера',
  PRIMARY KEY (`id_server`),
  INDEX `fk_servers_games1_idx` (`fk_games_id` ASC) VISIBLE,
  INDEX `idx_server_name` (`server_name` ASC) VISIBLE,
  CONSTRAINT `fk_servers_games1`
    FOREIGN KEY (`fk_games_id`)
    REFERENCES `bm_db`.`games` (`id_game`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Основная информация о серверах';

-- -----------------------------------------------------
-- Table `bm_db`.`rust_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_servers` (
  `fk_id_servers` VARCHAR(50) NOT NULL COMMENT 'ID сервера (ссылка на servers.id_server)',
  `is_pve` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг PVE сервера',
  `official` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг официального сервера',
  `description` LONGTEXT NULL DEFAULT NULL COMMENT 'Описание сервера',
  `modded` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг модифицированного сервера',
  `gamemode` VARCHAR(50) NULL DEFAULT NULL COMMENT 'Режим игры',
  `steam_id` BIGINT NULL DEFAULT NULL COMMENT 'Steam ID сервера',
  `next_wipe_date` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата следующего вайпа',
  `next_wipe_type` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Тип следующего вайпа',
  `last_wipe_date` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата последнего вайпа',
  PRIMARY KEY (`fk_id_servers`),
  INDEX `fk_rust_servers_servers1_idx` (`fk_id_servers` ASC) VISIBLE,
  CONSTRAINT `fk_rust_servers_servers1`
    FOREIGN KEY (`fk_id_servers`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Дополнительная информация о Rust серверах';

-- -----------------------------------------------------
-- Table `bm_db`.`server_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`server_filters` (
  `id_filter` INT NOT NULL AUTO_INCREMENT COMMENT 'ID фильтра сервера',
  `fk_servers_id` VARCHAR(50) NOT NULL DEFAULT '0' COMMENT 'ID сервера (0 для универсального фильтра)',
  `player_count` INT NULL DEFAULT -1 COMMENT 'Минимальное количество игроков (-1 = отключено)',
  `max_player_count` INT NULL DEFAULT -1 COMMENT 'Максимальное количество игроков (-1 = отключено)',
  `status_check` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения статуса',
  `ip_port_check` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения IP/порта',
  `private_check` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения приватности',
  PRIMARY KEY (`id_filter`),
  INDEX `fk_server_filter_servers1_idx` (`fk_servers_id` ASC) VISIBLE,
  CONSTRAINT `fk_server_filter_servers1`
    FOREIGN KEY (`fk_servers_id`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Фильтры для серверов';

-- -----------------------------------------------------
-- Table `bm_db`.`rust_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_filters` (
  `id_filter` INT NOT NULL AUTO_INCREMENT COMMENT 'ID Rust фильтра',
  `fk_server_filters_id` INT NOT NULL COMMENT 'ID связанного server_filter',
  `queued_players_count` INT NULL DEFAULT -1 COMMENT 'Минимальное количество игроков в очереди (-1 = отключено)',
  `last_wipe_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения последнего вайпа',
  `next_wipe_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения следующего вайпа',
  `pve_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения PVE статуса',
  `url_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения URL сервера',
  `map_url_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения URL карты',
  `map_image_check` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Проверка изменения изображения карты (map_thumbnailUrl)',
  PRIMARY KEY (`id_filter`),
  INDEX `fk_rust_filters_server_filter1_idx` (`fk_server_filters_id` ASC) VISIBLE,
  CONSTRAINT `fk_rust_filters_server_filter1`
    FOREIGN KEY (`fk_server_filters_id`)
    REFERENCES `bm_db`.`server_filters` (`id_filter`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Дополнительные фильтры для Rust серверов';

-- -----------------------------------------------------
-- Table `bm_db`.`players`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players` (
  `id_players` VARCHAR(50) NOT NULL COMMENT 'ID игрока на BattleMetrics (может быть строкой)',
  `nickname` VARCHAR(100) NOT NULL COMMENT 'Никнейм игрока',
  `positive_match` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг прямого совпадения данных',
  `private` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг приватного профиля',
  `created_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата создания профиля',
  `updated_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата последнего обновления',
  PRIMARY KEY (`id_players`),
  INDEX `idx_player_nickname` (`nickname` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Информация об игроках';

-- -----------------------------------------------------
-- Table `bm_db`.`player_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`player_filters` (
  `id_player_filter` INT NOT NULL AUTO_INCREMENT COMMENT 'ID фильтра игрока',
  `fk_id_players` VARCHAR(50) NOT NULL DEFAULT '0' COMMENT 'ID игрока (0 для универсального фильтра)',
  `player_name_changed` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения имени игрока',
  `player_private_changed` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения приватности профиля',
  `proofile_link_changed` TINYINT(1) NULL DEFAULT 0 COMMENT 'Проверка изменения ссылки на профиль (не используется)',
  PRIMARY KEY (`id_player_filter`),
  INDEX `fk_player_filters_players1_idx` (`fk_id_players` ASC) VISIBLE,
  CONSTRAINT `fk_player_filters_players1`
    FOREIGN KEY (`fk_id_players`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Фильтры для игроков';

-- -----------------------------------------------------
-- Table `bm_db`.`filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`filters` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT 'ID фильтра',
  `object_type` VARCHAR(20) NOT NULL COMMENT 'Тип объекта (server, player)',
  `fk_server_filters_id` INT NULL DEFAULT NULL COMMENT 'ID server_filter (если тип = server)',
  `fk_id_player_filter` INT NULL DEFAULT NULL COMMENT 'ID player_filter (если тип = player)',
  PRIMARY KEY (`id`),
  INDEX `fk_filters_server_filters1_idx` (`fk_server_filters_id` ASC) VISIBLE,
  INDEX `fk_filters_player_filters1_idx` (`fk_id_player_filter` ASC) VISIBLE,
  CONSTRAINT `fk_filters_server_filters1`
    FOREIGN KEY (`fk_server_filters_id`)
    REFERENCES `bm_db`.`server_filters` (`id_filter`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_filters_player_filters1`
    FOREIGN KEY (`fk_id_player_filter`)
    REFERENCES `bm_db`.`player_filters` (`id_player_filter`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `chk_filter_type`
    CHECK (`object_type` IN ('server', 'player')))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Универсальная таблица фильтров';

-- -----------------------------------------------------
-- Table `bm_db`.`profiles_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`profiles_filters` (
  `id_conn` INT NOT NULL AUTO_INCREMENT COMMENT 'ID связи профиль-фильтр',
  `fk_id_profile` VARCHAR(50) NOT NULL COMMENT 'ID профиля пользователя',
  `fk_filters_id` INT NOT NULL COMMENT 'ID фильтра',
  PRIMARY KEY (`id_conn`),
  INDEX `fk_profiles_filters_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  INDEX `fk_profiles_filters_filters1_idx` (`fk_filters_id` ASC) VISIBLE,
  UNIQUE INDEX `idx_profile_filter` (`fk_id_profile` ASC, `fk_filters_id` ASC) VISIBLE,
  CONSTRAINT `fk_profiles_filters_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_profiles_filters_filters1`
    FOREIGN KEY (`fk_filters_id`)
    REFERENCES `bm_db`.`filters` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Связь профилей пользователей с фильтрами';

-- -----------------------------------------------------
-- Table `bm_db`.`players_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players_servers` (
  `id_conn` INT NOT NULL AUTO_INCREMENT COMMENT 'ID связи игрок-сервер',
  `fk_id_server` VARCHAR(50) NOT NULL COMMENT 'ID сервера',
  `fk_id_players` VARCHAR(50) NOT NULL COMMENT 'ID игрока',
  `is_online` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг онлайн статуса',
  `time_played` INT NOT NULL DEFAULT 0 COMMENT 'Время игры в секундах',
  PRIMARY KEY (`id_conn`),
  INDEX `fk_players_servers_servers1_idx` (`fk_id_server` ASC) VISIBLE,
  INDEX `fk_players_servers_players1_idx` (`fk_id_players` ASC) VISIBLE,
  UNIQUE INDEX `idx_player_server` (`fk_id_server` ASC, `fk_id_players` ASC) VISIBLE,
  CONSTRAINT `fk_players_servers_servers1`
    FOREIGN KEY (`fk_id_server`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_players_servers_players1`
    FOREIGN KEY (`fk_id_players`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Связь игроков с серверами';

-- -----------------------------------------------------
-- Table `bm_db`.`logs_sql`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`logs_sql` (
  `id_log` INT NOT NULL AUTO_INCREMENT COMMENT 'ID лога',
  `object` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Объект, который вызвал действие',
  `action` VARCHAR(512) NULL DEFAULT NULL COMMENT 'Название действия',
  `is_error` TINYINT(1) NULL DEFAULT 0 COMMENT 'Флаг ошибки',
  `comment` LONGTEXT NULL DEFAULT NULL COMMENT 'Комментарий к действию',
  `stage` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Этап выполнения',
  `log_date` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Дата и время лога',
  `command` LONGTEXT NULL DEFAULT NULL COMMENT 'SQL команда (если применимо)',
  `result` LONGTEXT NULL DEFAULT NULL COMMENT 'Результат выполнения',
  `fk_id_profile` VARCHAR(50) NULL DEFAULT NULL COMMENT 'ID профиля (если применимо)',
  PRIMARY KEY (`id_log`),
  INDEX `fk_logs_sql_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  INDEX `idx_log_date` (`log_date` DESC) VISIBLE,
  INDEX `idx_is_error` (`is_error` ASC) VISIBLE,
  CONSTRAINT `fk_logs_sql_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE SET NULL
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Логи SQL операций и ошибок';

-- -----------------------------------------------------
-- Table `bm_db`.`logs`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`logs` (
  `id_log` INT NOT NULL AUTO_INCREMENT COMMENT 'ID лога',
  `fk_id_profile` VARCHAR(50) NOT NULL COMMENT 'ID профиля пользователя',
  `message_to_bot` LONGTEXT NOT NULL COMMENT 'Сообщение пользователя боту',
  `message_from_bot` LONGTEXT NULL DEFAULT NULL COMMENT 'Ответ бота пользователю',
  `error_status` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг ошибки',
  `error_log` LONGTEXT NULL DEFAULT NULL COMMENT 'Текст ошибки',
  `log_date` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Дата и время лога',
  PRIMARY KEY (`id_log`),
  INDEX `fk_logs_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  INDEX `idx_log_date` (`log_date` DESC) VISIBLE,
  CONSTRAINT `fk_logs_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Логи взаимодействия пользователей с ботом';

-- -----------------------------------------------------
-- Table `bm_db`.`suggestions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`suggestions` (
  `id_suggestions` INT NOT NULL AUTO_INCREMENT COMMENT 'ID предложения',
  `fk_id_profile` VARCHAR(50) NOT NULL COMMENT 'ID профиля пользователя',
  `msg_txt` LONGTEXT NOT NULL COMMENT 'Текст предложения/отчета',
  `isAnswered` TINYINT(1) NULL DEFAULT 0 COMMENT 'Флаг ответа на предложение',
  `isAccepted` TINYINT(1) NULL DEFAULT 0 COMMENT 'Флаг принятия предложения',
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Дата создания',
  `answered_at` TIMESTAMP NULL DEFAULT NULL COMMENT 'Дата ответа',
  PRIMARY KEY (`id_suggestions`),
  INDEX `fk_suggestions_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  INDEX `idx_created_at` (`created_at` DESC) VISIBLE,
  CONSTRAINT `fk_suggestions_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci
COMMENT = 'Предложения и отчеты пользователей';

-- -----------------------------------------------------
-- Вставка начальных данных
-- -----------------------------------------------------

-- Вставка игры Rust
INSERT IGNORE INTO `bm_db`.`games` (`id_game`, `game_name`) VALUES (1, 'rust');

-- Вставка игры Arma 3 (если нужно)
INSERT IGNORE INTO `bm_db`.`games` (`id_game`, `game_name`) VALUES (2, 'arma3');

-- -----------------------------------------------------
-- Восстановление настроек SQL
-- -----------------------------------------------------

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;

