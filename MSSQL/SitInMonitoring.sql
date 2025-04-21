CREATE DATABASE SitInMonitoring;

USE SitInMonitoring;

-- Users Table
CREATE TABLE Users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id NVARCHAR(50) UNIQUE NOT NULL,
    password NVARCHAR(255) NOT NULL,
    email NVARCHAR(100) UNIQUE NOT NULL,
    lastname NVARCHAR(50) NOT NULL,
    firstname NVARCHAR(50) NOT NULL,
    middlename NVARCHAR(50),
    course NVARCHAR(50),
    yearlevel NVARCHAR(20),
    role NVARCHAR(20) NOT NULL DEFAULT 'student',
    date_registered DATETIME DEFAULT GETDATE()
);

-- Sessions Table
CREATE TABLE Sessions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    remaining_sessions INT NOT NULL DEFAULT 30,
    FOREIGN KEY (user_id) REFERENCES Users(id)
);

-- Reservation Table
CREATE TABLE Reservation (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id NVARCHAR(50) NOT NULL,
    lastname NVARCHAR(50) NOT NULL,
    firstname NVARCHAR(50) NOT NULL,
    date NVARCHAR(20) NOT NULL,
    time NVARCHAR(20) NOT NULL,
    purpose NVARCHAR(100) NOT NULL,
    lab NVARCHAR(50) NOT NULL,
    available_pc NVARCHAR(50) NOT NULL,
    status NVARCHAR(50) DEFAULT 'Pending',
    time_in NVARCHAR(20),
    time_out NVARCHAR(20),
    FOREIGN KEY (student_id) REFERENCES Users(student_id)
);

-- Labs Table
CREATE TABLE Labs (
    id INT IDENTITY(1,1) PRIMARY KEY,
    lab_name NVARCHAR(50) NOT NULL
);

-- PCs Table
CREATE TABLE PCs (
    id INT IDENTITY(1,1) PRIMARY KEY,
    lab_id INT NOT NULL,
    pc_name NVARCHAR(50) NOT NULL,
    is_available BIT NOT NULL DEFAULT 1, -- BIT is used for boolean in MSSQL
    FOREIGN KEY (lab_id) REFERENCES Labs(id)
);

-- Announcements Table
CREATE TABLE Announcements (
    id INT IDENTITY(1,1) PRIMARY KEY,
    announcement_text NVARCHAR(MAX) NOT NULL, -- NVARCHAR(MAX) for large text
    created_at DATETIME DEFAULT GETDATE()
);

-- Feedback Table
CREATE TABLE Feedback (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id NVARCHAR(50) NOT NULL,
    lab NVARCHAR(50) NOT NULL,
    feedback_text NVARCHAR(MAX) NOT NULL,
    created_at DATETIME DEFAULT GETDATE()
);


-- Insert sample labs
INSERT INTO Labs (lab_name) VALUES
    ('526'),
    ('Mac Lab'),
    ('544'),
    ('523'),
    ('524');

-- Check if the lab column exists before adding it
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID(N'[dbo].[Feedback]') 
    AND name = 'lab'
)
BEGIN
    ALTER TABLE Feedback ADD lab NVARCHAR(50) NOT NULL DEFAULT 'Unknown';
END

Select * From Users;
Select * From Announcements;
Select * From Feedback;
Select * From Labs;
Select * From Reservation;
Select * From Sessions;
Select * From PCs;

UPDATE Feedback f
SET f.lab = (SELECT r.lab FROM Reservation r 
             WHERE r.student_id = f.student_id 
             ORDER BY r.id DESC LIMIT 1)
WHERE f.lab = 'Unknown' OR f.lab IS NULL;

-- Update existing feedback records with correct lab information
UPDATE f
SET f.lab = r.lab
FROM Feedback f
JOIN Reservation r ON f.student_id = r.student_id
WHERE (f.lab = 'Unknown' OR f.lab IS NULL)
AND r.id = (
    SELECT TOP 1 id 
    FROM Reservation 
    WHERE student_id = f.student_id 
    ORDER BY id DESC
);