-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema bm_db
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema bm_db
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `bm_db` DEFAULT CHARACTER SET utf8 ;
USE `bm_db` ;

-- -----------------------------------------------------
-- Table `bm_db`.`profiles`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`profiles` (
  `id_profile` INT NOT NULL,
  `profile_nickname` VARCHAR(50) NULL DEFAULT 'None',
  `profile_name` VARCHAR(50) NULL DEFAULT 'None',
  `profile_surname` VARCHAR(50) NULL DEFAULT 'None',
  `bot_banned` TINYINT(1) NULL DEFAULT 0,
  PRIMARY KEY (`id_profile`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`games`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`games` (
  `id_game` INT NOT NULL AUTO_INCREMENT,
  `game_name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`id_game`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`rust_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_servers` (
  `id_server` INT NOT NULL,
  `is_pve` TINYINT(1) NOT NULL,
  `official` TINYINT(1) NOT NULL,
  `description` LONGTEXT NULL,
  `modded` TINYINT(1) NOT NULL,
  `gamemode` VARCHAR(20) NOT NULL,
  `steam_id` INT NOT NULL,
  `next_wipe_date` TIMESTAMP NOT NULL,
  `next_wipe_type` VARCHAR(10) NOT NULL,
  PRIMARY KEY (`id_server`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`servers` (
  `id_server` INT NOT NULL,
  `fk_games_id` INT NOT NULL,
  `server_name` VARCHAR(100) NOT NULL,
  `rank` INT NOT NULL,
  `private` TINYINT NOT NULL,
  `country` VARCHAR(25) NOT NULL,
  `rust_server_id` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id_server`),
  INDEX `fk_servers_games1_idx` (`fk_games_id` ASC) VISIBLE,
  INDEX `fk_servers_rust_servers1_idx` (`rust_server_id` ASC) VISIBLE,
  CONSTRAINT `fk_servers_games1`
    FOREIGN KEY (`fk_games_id`)
    REFERENCES `bm_db`.`games` (`id_game`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_servers_rust_servers1`
    FOREIGN KEY (`rust_server_id`)
    REFERENCES `bm_db`.`rust_servers` (`id_server`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`server_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`server_filters` (
  `id_filter` INT NOT NULL AUTO_INCREMENT,
  `fk_servers_id` INT NOT NULL,
  `player_count` INT NULL DEFAULT -1,
  `max_player_count` INT NULL DEFAULT -1,
  `status_check` TINYINT(1) NULL DEFAULT 0,
  `ip_port_check` TINYINT(1) NULL DEFAULT 0,
  `private_check` TINYINT(1) NULL DEFAULT 0,
  PRIMARY KEY (`id_filter`),
  INDEX `fk_server_filter_servers1_idx` (`fk_servers_id` ASC) VISIBLE,
  CONSTRAINT `fk_server_filter_servers1`
    FOREIGN KEY (`fk_servers_id`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`rust_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`rust_filters` (
  `id_filter` INT NOT NULL AUTO_INCREMENT,
  `fk_server_filters_id` INT NOT NULL,
  `queued_players_count` TINYINT(1) NOT NULL,
  `last_wipe_check` TINYINT(1) NOT NULL,
  `pve_check` TINYINT(1) NOT NULL,
  `url_check` TINYINT(1) NOT NULL,
  `map_url_check` TINYINT(1) NOT NULL,
  `map_image_check` TINYINT(1) NOT NULL,
  PRIMARY KEY (`id_filter`),
  INDEX `fk_rust_filters_server_filter1_idx` (`fk_server_filters_id` ASC) VISIBLE,
  CONSTRAINT `fk_rust_filters_server_filter1`
    FOREIGN KEY (`fk_server_filters_id`)
    REFERENCES `bm_db`.`server_filters` (`id_filter`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`logs_sql`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`logs_sql` (
  `id_log` INT NOT NULL AUTO_INCREMENT,
  `object` VARCHAR(100) NULL DEFAULT NULL,
  `action` VARCHAR(512) NULL DEFAULT NULL,
  `is_error` TINYINT(1) NULL DEFAULT 0,
  `comment` LONGTEXT NULL DEFAULT NULL,
  `stage` VARCHAR(50) NULL DEFAULT NULL,
  `log_date` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `command` LONGTEXT NULL DEFAULT NULL,
  `result` LONGTEXT NULL DEFAULT NULL,
  `fk_id_profile` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id_log`),
  INDEX `fk_logs_sql_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  CONSTRAINT `fk_logs_sql_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`players`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players` (
  `id_players` INT NOT NULL,
  `nickname` VARCHAR(45) NOT NULL,
  `positive_match` TINYINT(1) NOT NULL,
  `private` TINYINT(1) NOT NULL,
  PRIMARY KEY (`id_players`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`player_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`player_filters` (
  `id_player_filter` INT NOT NULL AUTO_INCREMENT,
  `fk_id_players` INT NOT NULL,
  `player_name_changed` TINYINT(1) NULL DEFAULT 0,
  `player_private_changed` TINYINT(1) NULL DEFAULT 0,
  `proofile_link_changed` TINYINT(1) NULL DEFAULT 0,
  PRIMARY KEY (`id_player_filter`),
  INDEX `fk_player_filters_players1_idx` (`fk_id_players` ASC) VISIBLE,
  CONSTRAINT `fk_player_filters_players1`
    FOREIGN KEY (`fk_id_players`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`filters` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `object_type` VARCHAR(20) NOT NULL,
  `fk_server_filters_id` INT NULL,
  `fk_id_player_filter` INT NULL,
  PRIMARY KEY (`id`),
  INDEX `fk_filters_server_filters1_idx` (`fk_server_filters_id` ASC) VISIBLE,
  INDEX `fk_filters_player_filters1_idx` (`fk_id_player_filter` ASC) VISIBLE,
  CONSTRAINT `fk_filters_server_filters1`
    FOREIGN KEY (`fk_server_filters_id`)
    REFERENCES `bm_db`.`server_filters` (`id_filter`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_filters_player_filters1`
    FOREIGN KEY (`fk_id_player_filter`)
    REFERENCES `bm_db`.`player_filters` (`id_player_filter`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`profiles_filters`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`profiles_filters` (
  `id_conn` INT NOT NULL AUTO_INCREMENT,
  `fk_id_profile` INT NOT NULL,
  `fk_filters_id` INT NOT NULL,
  PRIMARY KEY (`id_conn`),
  INDEX `fk_profiles_filters_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  INDEX `fk_profiles_filters_filters1_idx` (`fk_filters_id` ASC) VISIBLE,
  CONSTRAINT `fk_profiles_filters_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_profiles_filters_filters1`
    FOREIGN KEY (`fk_filters_id`)
    REFERENCES `bm_db`.`filters` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`players_servers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`players_servers` (
  `id_conn` INT NOT NULL AUTO_INCREMENT,
  `fk_id_server` INT NOT NULL,
  `fk_id_players` INT NOT NULL,
  `is_online` TINYINT(1) NOT NULL,
  `time_played` INT NOT NULL,
  PRIMARY KEY (`id_conn`),
  INDEX `fk_players_servers_servers1_idx` (`fk_id_server` ASC) VISIBLE,
  INDEX `fk_players_servers_players1_idx` (`fk_id_players` ASC) VISIBLE,
  CONSTRAINT `fk_players_servers_servers1`
    FOREIGN KEY (`fk_id_server`)
    REFERENCES `bm_db`.`servers` (`id_server`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_players_servers_players1`
    FOREIGN KEY (`fk_id_players`)
    REFERENCES `bm_db`.`players` (`id_players`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`logs`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`logs` (
  `id_log` INT NOT NULL AUTO_INCREMENT,
  `fk_id_profile` INT NOT NULL,
  `message_to_bot` LONGTEXT NOT NULL,
  `message_from_bot` LONGTEXT NULL,
  `error_status` TINYINT(1) NOT NULL,
  `error_log` LONGTEXT NULL,
  PRIMARY KEY (`id_log`),
  INDEX `fk_logs_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  CONSTRAINT `fk_logs_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `bm_db`.`suggestions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `bm_db`.`suggestions` (
  `id_suggestions` INT NOT NULL,
  `fk_id_profile` INT NOT NULL,
  `msg_txt` LONGTEXT NOT NULL,
  `isAnswered` TINYINT(1) NULL DEFAULT 0,
  `isAccepted` TINYINT(1) NULL DEFAULT 0,
  PRIMARY KEY (`id_suggestions`),
  INDEX `fk_suggestions_profiles1_idx` (`fk_id_profile` ASC) VISIBLE,
  CONSTRAINT `fk_suggestions_profiles1`
    FOREIGN KEY (`fk_id_profile`)
    REFERENCES `bm_db`.`profiles` (`id_profile`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
