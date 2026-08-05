# System Model

This is the system model.

## Data Model

```mermaid
erDiagram
    ORGANIZATION ||--o{ ORG_UNIT : contains
    ORGANIZATION ||--o{ PLANT : owns
    ORGANIZATION ||--o{ PLACE : manages
    ORGANIZATION ||--o{ PLANT_LIST : maintains
    ORGANIZATION ||--o{ PUBLIC_PAGE : publishes

    ORG_UNIT ||--o{ PLANT : curates
    PLACE ||--o{ PLACE : contains
    PLACE ||--o{ PLANT : locates

    PLANT }o--|| SYSTEM_TAXON : "required taxon_id"
    PLANT ||--o{ PHOTO : documents
    PLANT }o--o{ PLANT_LIST : included_in

    SYSTEM_TAXON ||--o| GLOBAL_TAXON : "species subtype"
    SYSTEM_TAXON ||--o| CULTIVATED_ENTITY : "cultivar/grex subtype"

    PUBLIC_PAGE ||--o{ PLANT_LIST : exposes
    PUBLIC_PAGE ||--o{ PLANT : exposes_selected

    ORGANIZATION {
        uuid id PK
        string public_name
        string slug
        string visibility
    }

    ORG_UNIT {
        uuid id PK
        uuid organization_id FK
        uuid parent_id FK
        string name
    }

    PLANT {
        uuid id PK
        uuid organization_id FK
        uuid org_unit_id FK
        uuid place_id FK
        uuid taxon_id FK "mandatory"
        string accession_number
        string individual_code
        string status
        string provenance_type
        geometry point
        jsonb custom_fields
    }

    SYSTEM_TAXON {
        uuid id PK
        string display_name
        string normalized_name
        string taxon_type
        string rank
    }

    GLOBAL_TAXON {
        uuid id PK
        uuid system_taxon_id FK
        string id
        string ipni_id
        string family
        string genus
        string species_epithet
        string scientific_name
    }

    CULTIVATED_ENTITY {
        uuid id PK
        uuid system_taxon_id FK
        string genus
        string cultivar_or_grex_name
        string breeder_name
        string registrar_name
        int registration_year
        string visibility_scope
    }

    PLACE {
        uuid id PK
        uuid organization_id FK
        uuid parent_id FK
        string name
        geometry point
        geometry polygon
    }

    PLANT_LIST {
        uuid id PK
        uuid organization_id FK
        string name
        string list_type
        string visibility
    }

    PHOTO {
        uuid id PK
        uuid PLANT_id FK
        string caption
        string photo_tag
        boolean publication_allowed
    }

    PUBLIC_PAGE {
        uuid id PK
        uuid organization_id FK
        string slug
        boolean visible
    }
```
