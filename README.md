# Student Record System

A centralized web-based application for managing student academic records, course enrollment, attendance, examination results, faculty operations, and fee management.

The **Student Record System (SRS)** is developed to simplify academic administration by bringing students, faculty members, and administrators together on a single platform.

The application provides role-based access, allowing each user to perform operations according to their responsibilities.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Objectives](#objectives)
- [Features](#features)
- [User Roles](#user-roles)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Demo Accounts](#demo-accounts)
- [Testing](#testing)
- [Payment Module](#payment-module)
- [Project Documentation](#project-documentation)
- [Future Enhancements](#future-enhancements)
- [Contributors](#contributors)

---

## Project Overview

Educational institutions manage large amounts of student information, including personal details, course registrations, attendance, examination marks, and financial records.

Managing these records through disconnected systems can lead to duplication, inconsistencies, and difficulties in accessing information.

The Student Record System addresses these challenges through a centralized platform that supports:

- Digital student record management.
- Course and enrollment administration.
- Faculty and academic management.
- Attendance tracking.
- Examination and grade management.
- Fee and payment management.
- Academic reporting and transcript generation.

---

## Objectives

- Centralize student academic and administrative information.
- Provide secure, role-based access to system functionality.
- Simplify course enrollment and faculty assignment.
- Improve attendance and examination record management.
- Provide transparent grade review and approval workflows.
- Automate fee invoice and payment-related operations.
- Generate downloadable academic reports and transcripts.

---

## Features

### 1. Administrator Module

Administrators have access to institutional management functionality.

- Create and manage user accounts.
- Manage student and faculty information.
- Create and manage courses.
- Assign faculty members to courses.
- Configure course prerequisites.
- Manage enrollment windows and credit limits.
- Approve examination marks.
- View grade change history.
- Manage grade review requests.
- Configure grade review periods.
- Manage fee structures and invoices.
- Configure fee reminders and enrollment thresholds.
- Manage student fee overrides.
- Approve or reject profile change requests.
- Upload and manage student documents.
- Generate academic reports and transcripts.
- Access audit event records.

### 2. Faculty Module

Faculty members can manage their assigned academic responsibilities.

- View the course catalogue.
- Access course-wise student rosters.
- Record student attendance.
- View attendance summaries.
- Submit internal and end-semester marks.
- Modify examination marks according to application rules.

### 3. Student Module

Students can access their academic and administrative information.

- View personal profile information.
- Browse available courses.
- View current enrollments.
- Access attendance records.
- View examination results.
- Check GPA information.
- Download academic transcripts.
- Submit grade review requests.
- View fee invoices.
- Initiate and complete mock payments.
- Download payment receipts.
- Access profile documents.
- Submit profile change requests.

---

## User Roles

| Role | Responsibilities |
|---|---|
| Administrator | Manages users, courses, academic records, fees, reports, and system configuration. |
| Faculty | Manages course attendance and student examination marks. |
| Student | Accesses academic records, attendance, results, transcripts, and fee information. |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Backend | Python, Flask |
| Database | MySQL |
| ORM | SQLAlchemy |
| API Communication | REST API |
| Containerization | Docker |
| Container Orchestration | Docker Compose |
| Backend Testing | Pytest |
| Payment Integration | Mock Payment Gateway |

---

## System Architecture

The application follows a client-server architecture.

```text
                 ┌──────────────────────┐
                 │        Users         │
                 │                      │
                 │ Admin / Faculty /    │
                 │       Student        │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │    React Frontend    │
                 │                      │
                 │   User Interface     │
                 └──────────┬───────────┘
                            │
                         REST API
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Flask Backend     │
                 │                      │
                 │ Authentication       │
                 │ Business Logic       │
                 │ Role-based Access    │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │    MySQL Database    │
                 │                      │
                 │ Student Records      │
                 │ Courses and Marks    │
                 │ Attendance and Fees  │
                 └──────────────────────┘
```

Docker Compose manages the application services and database environment.

---

## Project Structure

```text
Student-Record-System/
│
├── .github/
│
├── backend/
│   ├── app/
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── attendance/
│   │   ├── common/
│   │   ├── course/
│   │   ├── enrollment/
│   │   ├── fees/
│   │   ├── grades/
│   │   ├── health/
│   │   ├── profile/
│   │   ├── reports/
│   │   └── reviews/
│   │
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── run.py
│   ├── seed.py
│   └── seed_demo.py
│
├── frontend/
│
├── docs/
│   └── performance/
│
├── perf/
│
├── SAD_Group6_Student_Record_System.docx
├── SRS_Student_Record_System_Group_6.pdf
├── Test_Plan_Student_Record_System_Group_6.docx
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

Install the following tools:

- Git
- Docker Desktop
- Node.js and npm
- Python 3.10 or later (if running the backend outside Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/Student-Record-System/Student-Record-System.git
```

Navigate into the project:

```bash
cd Student-Record-System
```

### 2. Configure Environment Variables

Create the required environment files using the provided `.env.example` configuration.

Configure the database connection and application-specific settings.

Do not commit actual credentials or secret keys.

### 3. Start Docker Services

From the project root:

```bash
docker compose up -d
```

Check the running containers:

```bash
docker compose ps
```

Ensure the MySQL database is healthy and the Flask backend is running.

### 4. Start the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed in the terminal to access the application.

---

## Environment Configuration

Example database configuration:

```env
MYSQL_DATABASE=srs_db
MYSQL_USER=srs_user
MYSQL_PASSWORD=your_database_password
MYSQL_ROOT_PASSWORD=your_root_password
```

The backend database connection should use the Docker service hostname:

```env
DATABASE_URL=mysql+pymysql://srs_user:your_database_password@db:3306/srs_db
```

Configure the remaining application-specific variables using the backend environment example.

**Security note:** Never commit `.env` files, database passwords, secret keys, or database backups to the repository.

---

## Database Setup

The project includes seed scripts for administrator setup and demonstration data.

Run the administrator seed script:

```bash
docker compose exec backend python seed.py
```

Run the demonstration data seed script:

```bash
docker compose exec backend python seed_demo.py
```

The demonstration dataset includes:

- Administrator account.
- Faculty accounts.
- Student accounts.
- Course records.
- Course enrollments.
- Attendance records.
- Examination marks.
- Fee structures.
- Fee invoices.
- Grade review requests.

Run these scripts during initial setup or when intentionally refreshing demo data. Avoid rerunning them on a database containing records that need to be preserved.

---

## Running the Application

Start all configured Docker services:

```bash
docker compose up -d
```

Check service status:

```bash
docker compose ps
```

View backend logs:

```bash
docker compose logs -f backend
```

View database logs:

```bash
docker compose logs -f db
```

Stop the application:

```bash
docker compose stop
```

Restart existing containers:

```bash
docker compose start
```

**Database persistence:** MySQL data is stored in a Docker volume. Stopping containers or restarting the computer does not normally delete stored records. Avoid `docker compose down -v`, as it removes Compose-managed volumes.

---

## Demo Accounts

The demonstration environment includes predefined accounts for testing different roles.

| Role | Login ID |
|---|---|
| Administrator | `admin` |
| Faculty | `FAC001` |
| Faculty | `FAC002` |
| Student | `PES2UG24CS000` |
| Student | `PES2UG24CS001` |
| Student | `PES2UG24CS002` |
| Student | `PES2UG24CS003` |

Passwords are configured through the demonstration seed setup and should not be published in the repository.

---

## Testing

Backend tests use Pytest.

Run backend tests:

```bash
cd backend
python -m pytest
```

Build the frontend:

```bash
cd frontend
npm ci
npm run build
```

These commands can be used to validate application changes before submitting pull requests.

---

## Payment Module

The application includes a mock payment gateway for testing and demonstration.

The payment workflow supports:

1. Viewing fee invoices.
2. Initiating payments.
3. Creating mock gateway orders.
4. Completing simulated payment transactions.
5. Confirming payment status.
6. Generating downloadable payment receipts.

**Note:** The mock gateway does not process real financial transactions or charge actual money.

---

## Project Documentation

The repository includes supporting software engineering documentation:

| Document | Description |
|---|---|
| Software Requirements Specification (SRS) | Defines the system requirements and expected functionality. |
| Software Architecture Document (SAD) | Describes the system architecture and design decisions. |
| Test Plan | Documents the planned testing activities and validation approach. |
| Performance Documentation | Contains performance-related measurements and supporting information. |

---

## Future Enhancements

Potential improvements include:

- Integration with a real payment gateway.
- Enhanced academic analytics and dashboards.
- Automated email and notification services.
- Improved reporting and data visualization.
- Expanded automated test coverage.
- Enhanced security monitoring.
- Improved mobile responsiveness.

---

## Contributors

Developed collaboratively by the Student Record System project team.

- **Naija Hodigere** — Project coordination and Scrum Master.
- **M.B.Divyadharshini** — Developer.
- **Marapareddy Deekshitha** — Developer.
- **M S Nikhil Chowdhary** — Product Owner.

---

## Repository

GitHub: [Student-Record-System](https://github.com/Student-Record-System/Student-Record-System)

---

*Student Record System — Bringing academic and administrative records together in one platform.*