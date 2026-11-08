CREATE DATABASE IF NOT EXISTS `motel_python` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `motel_python`;

CREATE TABLE IF NOT EXISTS rooms (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	room_number VARCHAR(30) NOT NULL, 
	area NUMERIC(8, 2), 
	monthly_price NUMERIC(12, 0) NOT NULL, 
	electricity_price NUMERIC(10, 0) NOT NULL, 
	water_price NUMERIC(10, 0) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (room_number)
)

;

CREATE TABLE IF NOT EXISTS tenants (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_code VARCHAR(30) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	identity_number VARCHAR(30), 
	date_of_birth DATE, 
	address VARCHAR(255), 
	move_in_date DATE, 
	status VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (tenant_code), 
	UNIQUE (identity_number)
)

;

CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(190) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	`role` VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;

CREATE TABLE IF NOT EXISTS contracts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	contract_code VARCHAR(30) NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	room_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	monthly_price NUMERIC(12, 0) NOT NULL, 
	deposit NUMERIC(12, 0) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (contract_code), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(room_id) REFERENCES rooms (id)
)

;

CREATE TABLE IF NOT EXISTS invoices (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	invoice_code VARCHAR(30) NOT NULL, 
	contract_id INTEGER NOT NULL, 
	billing_month DATE NOT NULL, 
	room_charge NUMERIC(12, 0) NOT NULL, 
	old_electricity INTEGER NOT NULL, 
	new_electricity INTEGER NOT NULL, 
	electricity_charge NUMERIC(12, 0) NOT NULL, 
	water_charge NUMERIC(12, 0) NOT NULL, 
	service_charge NUMERIC(12, 0) NOT NULL, 
	total NUMERIC(12, 0) NOT NULL, 
	due_date DATE NOT NULL, 
	paid_at DATETIME, 
	status VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_contract_month UNIQUE (contract_id, billing_month), 
	UNIQUE (invoice_code), 
	FOREIGN KEY(contract_id) REFERENCES contracts (id)
)

;
