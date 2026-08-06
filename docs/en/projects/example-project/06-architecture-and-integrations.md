# Architecture and Integrations

This is architecture and integrations.

## Architecture

```mermaid
    C4Container
    title Container Diagram for Botanical SaaS MVP

    Person(user, "User")

    System_Boundary(sys, "System") {
      Container(spa, "SPA", "Angular 21", "User interface")
      Container(backend, "Backend", "Spring Boot", "Business logic")
      ContainerDb(reldb, "Database", "PostgreSQL + PostGIS", "Plants, places, users")
    }

  Rel(user, spa, "Manages plant collections")
  Rel(spa, backend, "API calls", "HTTPS REST")
  Rel(backend, reldb, "Reads/writes data", "SQL")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```
