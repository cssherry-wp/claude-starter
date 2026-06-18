---
name: sql-style
description: Enterprise SQL guidelines. Use when writing or reviewing SQL, schema definitions, or database migrations — covers naming, indexing, primary-key strategy, injection prevention, and best practices.
---

# Enterprise SQL Guidelines

## Naming Conventions

### Tables
- **Always use plural names**: `users`, `projects`, `organizations`, `products`
- Use lowercase with underscores for multi-word tables: `user_preferences`, `api_tokens`
- Never use singular table names: `user`, `project`

### Columns
- Use descriptive, lowercase names with underscores: `created_at`, `email_address`, `last_login_time`
- Boolean columns should use `is_`, `has_`, or `can_` prefixes: `is_active`, `has_verified_email`, `can_edit`
- Timestamp columns should use `_at` suffix: `created_at`, `updated_at`, `deleted_at`

### Foreign Keys
- **Use singular table name + `_id`**: `user_id`, `project_id`, `organization_id`
- Always name the foreign key constraint: `fk_projects_user_id` (format: `fk_<table>_<column>`)
- Add indexes on foreign key columns for performance: `idx_projects_user_id`

Example:
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    CONSTRAINT fk_projects_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_projects_user_id ON projects(user_id);
```

### Join Tables
- **Use plural names for both tables**: `organizations_users`, `projects_tags`, `roles_permissions`
- Order alphabetically when no natural hierarchy exists
- Include composite primary key on both foreign keys
- Always add foreign key constraints and indexes

Example:
```sql
CREATE TABLE organizations_users (
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, user_id),
    CONSTRAINT fk_organizations_users_org_id FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_organizations_users_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_organizations_users_user_id ON organizations_users(user_id);
CREATE INDEX idx_organizations_users_org_id ON organizations_users(organization_id);
```

## Index Strategy
- Always index foreign key columns
- Create composite indexes for frequently used column combinations
- Add partial indexes with WHERE clauses for filtered queries
- Index columns used in ORDER BY and GROUP BY operations

## Primary Key Strategy: UUID vs Integer

### Use UUIDs When:
✅ Distributed systems (multiple databases, sharding)
✅ Need globally unique identifiers
✅ Want to prevent ID enumeration attacks
✅ Merging data from multiple sources
✅ Public-facing IDs in URLs

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- ... other columns
);
```

### Use Auto-Incrementing Integers When:
✅ Single database instance
✅ Need better performance for joins (integers are faster than UUIDs)
✅ Need sequential ordering built into ID
✅ Storage size matters (UUIDs are 16 bytes vs 4/8 bytes for integers)

```sql
CREATE TABLE logs (
    id BIGSERIAL PRIMARY KEY,
    -- ... other columns
);
```

### Hybrid Approach
Use integer primary key for performance, add UUID for external references:

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    -- ... other columns
    CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_orders_public_id ON orders(public_id);
```

## SQL Injection Prevention

### CRITICAL Principles
- **NEVER** concatenate user input directly into SQL statements
- **ALWAYS** use parameterized queries with placeholders ($1, $2, ?, etc.)
- **ALWAYS** validate dynamic table/column names against a whitelist
- **ALWAYS** escape special characters (%, _) in LIKE patterns

### Vulnerable Pattern (DO NOT USE)
```sql
-- String concatenation with variables - DANGEROUS!
-- This allows injection attacks like: ' OR '1'='1' --
WHERE username = 'input_value_here';
```

### Safe Patterns (USE THESE)

**Dynamic Identifiers (Table/Column Names):**
```sql
-- When table/column names must be dynamic, use identifier quoting
-- and validate against a whitelist first
-- For PostgreSQL, use format() with %I for identifiers
format('CREATE INDEX idx_%I ON %I (%I)', index_name, table_name, column_name);
```

### Schema Design for Security

**Use Database Constraints:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    -- Prevent injection in CHECK constraints
    CONSTRAINT chk_username_format CHECK (username ~ '^[a-zA-Z0-9_-]{3,100}$'),
    CONSTRAINT chk_email_format CHECK (email ~ '^[^@]+@[^@]+\.[^@]+$')
);
```

**Principle of Least Privilege:**
```sql
-- Application user should have minimal permissions
-- Read-only operations:
GRANT SELECT ON TABLE users TO app_readonly;

-- Application operations:
GRANT SELECT, INSERT, UPDATE ON TABLE users TO app_user;
-- Do NOT grant: DROP, TRUNCATE, ALTER, DELETE (unless specifically needed)

-- Admin operations only:
GRANT ALL PRIVILEGES ON TABLE users TO app_admin;
```

## Additional Best Practices

### Use Constraints for Data Integrity
```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT chk_orders_status CHECK (status IN ('pending', 'processing', 'completed', 'cancelled')),
    CONSTRAINT chk_orders_amount CHECK (total_amount >= 0)
);
```

### Comments for Complex Logic
```sql
-- Soft delete pattern: deleted_at IS NULL means active record
-- This index supports queries for active users only
CREATE INDEX idx_users_active ON users(created_at) WHERE deleted_at IS NULL;
```

### Transaction Guidelines
- Use transactions for multi-step operations
- Keep transactions short to avoid lock contention
- Set appropriate isolation levels

```sql
BEGIN;
    UPDATE accounts SET balance = balance - 100 WHERE id = $1;
    UPDATE accounts SET balance = balance + 100 WHERE id = $2;
    INSERT INTO transactions (from_account_id, to_account_id, amount) VALUES ($1, $2, 100);
COMMIT;
```
