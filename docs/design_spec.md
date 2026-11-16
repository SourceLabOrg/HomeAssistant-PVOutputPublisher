# Design Specification: V2 Schema Migration & Unified Parameter Mapping

## 1. Overview & Motivation
The **HomeAssistant-PVOutputPublisher** integration is transitioning from its legacy v1 configuration schema to a **unified, parameter-aligned v2 schema**. 

### Legacy (v1) Limitations:
* **Ambiguous Heuristics:** Used generic "Primary" and "Secondary" solar sensor inputs and attempted runtime auto-detection of Power ($W$) vs. Energy ($Wh$).
* **Limited Extensibility:** Could not support PVOutput extended parameters (`v7`–`v12`), battery metrics (`b1`–`b6`), explicit net flag (`n=1`), or manual cumulative flag overrides (`c1=1`).
* **Lack of User Context:** No ability to save internal notes for multi-system setups.

### V2 Goals:
* **Unified UI:** A single, clear configuration form directly aligned with PVOutput's `addstatus.jsp` API parameters (`v1` through `v12`, `b1` through `b6`, `c1`, `n`), with free-tier parameters presented first and donation-only parameters (`v7`–`v12`, `b1`–`b6`) grouped in a collapsible section.
* **Zero Disruption via Migration:** Automated, robust migration from Schema v1 to v2 on install/startup (`async_migrate_entry`).
* **Local Notes Field:** User-facing internal notes field stored per system, omitted from API payloads.
* **Maintainable Architecture:** Single schema, single UI flow, single payload generator, automatic cleanup of orphaned status sensor entities, and high test coverage.

---

## 2. V2 Data Model & Configuration Keys

### 2.1 Configuration Keys (`const.py`)
```python
# Integration Scope
DOMAIN = "pvoutput_publisher"
CONF_API_KEY = "api_key"
CONF_SYSTEMS = "systems"

# System Common
CONF_NAME = "name"
CONF_SYSTEM_ID = "system_id"
CONF_FREQUENCY = "frequency"
CONF_NOTES = "notes"  # Internal notes (string, omitted from API)

# PVOutput 1-to-1 API Parameters
CONF_V1 = "v1"    # Energy Generation (Wh)
CONF_V2 = "v2"    # Power Generation (W)
CONF_V3 = "v3"    # Energy Consumption (Wh)
CONF_V4 = "v4"    # Power Consumption (W)
CONF_V5 = "v5"    # Temperature (°C / °F)
CONF_V6 = "v6"    # Voltage (V)
CONF_V7 = "v7"    # Extended Data 1
CONF_V8 = "v8"    # Extended Data 2
CONF_V9 = "v9"    # Extended Data 3
CONF_V10 = "v10"  # Extended Data 4
CONF_V11 = "v11"  # Extended Data 5
CONF_V12 = "v12"  # Extended Data 6

# PVOutput Battery Parameters
CONF_B1 = "b1"    # Battery Power (W)
CONF_B2 = "b2"    # State of Charge (%)
CONF_B3 = "b3"    # Battery Usable Capacity (Wh)
CONF_B4 = "b4"    # Battery Lifetime Charge (Wh)
CONF_B5 = "b5"    # Battery Lifetime Discharge (Wh)
CONF_B6 = "b6"    # Battery State (0-9)

# PVOutput Flags
CONF_C1 = "c1"    # Cumulative Energy Flag (bool -> &c1=1)
CONF_NET = "n"    # Net Power Flag (bool -> &n=1)

# Section Keys
CONF_DONATION_FIELDS = "donation_fields"

DEFAULT_FREQUENCY = "5"
PVOUTPUT_API_URL = "https://pvoutput.org/service/r2/addstatus.jsp"
PVOUTPUT_API_DOCS_URL = "https://pvoutput.org/help/api_specification.html#id2"
```

---

## 3. V1 to V2 Migration Logic (`async_migrate_entry`)

When Home Assistant loads a ConfigEntry with `entry.version == 1`, `async_migrate_entry(hass, entry)` is automatically invoked.

```
[V1 Config Entry]
  ├── api_key
  └── systems: [ { name, system_id, entity_id, secondary_entity_id, consumption_entity_id, temperature_entity_id, voltage_entity_id, frequency } ]
        │
        ▼ (async_migrate_entry)
  Inspect Entity Registry & Live States for each system:
    1. Primary (entity_id) & Secondary (secondary_entity_id):
       - If unit in [Wh, kWh, MWh] or device_class == energy:
           -> Map to v1
           -> Set c1 = True (since inverter energy sensors typically report lifetime totals)
       - If unit in [W, kW] or device_class == power:
           -> Map to v2
       - If state/registry unavailable: Name fallback ("energy" in id -> v1, else v2)
    2. Consumption (consumption_entity_id):
       - If unit in [Wh, kWh, MWh] or device_class == energy:
           -> Map to v3 (and set c1 = True if v1 is not set)
       - Else:
           -> Map to v4
    3. Temperature (temperature_entity_id) -> Map to v5
    4. Voltage (voltage_entity_id)         -> Map to v6
    5. Notes (notes)                       -> Initialize as "" (empty string)
    6. Extended (v7..v12) & Battery (b1..b6) -> Initialize as None
    7. Flags (c1, n)                       -> Default based on above or False
        │
        ▼
[V2 Config Entry (version=2)] Saved and returned to HA
```

### 3.1 Migration Safety Guarantees
* **Multi-Layer Introspection:** Checks 1) Live State machine (`hass.states`), 2) Entity Registry (`er.async_get(hass)`), and 3) Entity ID string heuristics (`"energy"`, `"power"`, `"kwh"`, `"w"`).
* **Non-Destructive:** If migration encounters an unrecognized structure, it preserves all existing keys while upgrading version to prevent data loss.
* **Test Verification:** Dedicated migration unit tests with mocked v1 entries verifying exact v2 outputs.

---

## 4. UI & Form Schema (`config_flow.py`)

Config flow and options flow use a single unified system schema `_get_system_schema(existing_data)`. Optional fields use `description={"suggested_value": ...}` rather than `default=...` so users can clear previously configured fields in the UI:

### Standard Parameters (Top-Level)
| Field | Type / Selector | Description |
| :--- | :--- | :--- |
| `name` | Text (Required, non-empty, stripped) | Friendly name of solar array |
| `system_id` | Text (Required, non-empty, stripped) | PVOutput System ID |
| `frequency` | Select (Required) | Push frequency (5m, 10m, 15m, 30m, 1h, 3h) |
| `notes` | Multiline Text (Optional) | Internal reference notes (not sent to API) |
| `v1` | Entity Selector (`sensor`, `device_class="energy"`) | **v1: Energy Generation** (Wh, converts kWh/MWh) |
| `v2` | Entity Selector (`sensor`, `device_class="power"`) | **v2: Power Generation** (W, converts kW) |
| `v3` | Entity Selector (`sensor`, `device_class="energy"`) | **v3: Energy Consumption** (Wh, converts kWh/MWh) |
| `v4` | Entity Selector (`sensor`, `device_class="power"`) | **v4: Power Consumption** (W, converts kW) |
| `v5` | Entity Selector (`sensor`, any device class) | **v5: Temperature** (°C / °F with auto-conversion) |
| `v6` | Entity Selector (`sensor`, `device_class="voltage"`) | **v6: Voltage** (V) |
| `c1` | Boolean Toggle | **Cumulative Flag (`c1=1`)**: Generation/Consumption is lifetime |
| `n` | Boolean Toggle | **Net Flag (`n=1`)**: Power generation is net export |

### Collapsible Donation Features Section (`donation_fields`)
Automatically starts collapsed unless at least one donation field (`v7`–`v12`, `b1`–`b6`) is configured on the system:

| Field | Type / Selector | Description |
| :--- | :--- | :--- |
| `v7` – `v12` | Entity Selector (`sensor`, `number`, `input_number`) | **v7 – v12: Extended Data** (Donation features) |
| `b1` | Entity Selector (`sensor`, `device_class="power"`) | **b1: Battery Power** (W, converts kW; + charge / - discharge) |
| `b2` | Entity Selector (`sensor`, `device_class="battery"`) | **b2: Battery State of Charge** (0–100%) |
| `b3` | Entity Selector (`sensor`, `number`, `input_number`) | **b3: Battery Usable Capacity** (Wh, converts kWh/MWh) |
| `b4` | Entity Selector (`sensor`, `device_class="energy"`) | **b4: Battery Lifetime Charge** (Wh, converts kWh/MWh) |
| `b5` | Entity Selector (`sensor`, `device_class="energy"`) | **b5: Battery Lifetime Discharge** (Wh, converts kWh/MWh) |
| `b6` | Entity Selector (`sensor`, `number`, `input_number`) | **b6: Battery State** (Numeric code 0–9) |

---

## 5. Payload Generation & Push Logic (`__init__.py`)

At scheduled intervals, for each configured v2 system:
1. Build timestamp: `d=YYYYMMDD&t=HH:MM`.
2. Inspect each mapped parameter (`v1`–`v12`, `b1`–`b6`):
   * Fetch entity state. Skip if `unknown`, `unavailable`, or invalid float.
   * Apply unit conversions:
     * `v1` / `v3`: `kwh` $\rightarrow \times 1000$, `mwh` $\rightarrow \times 10^6$. Output as integer.
     * `v2` / `v4`: `kw` / `kilowatt(s)` $\rightarrow \times 1000$. Output as integer.
     * `v5`: `°f` / `f` $\rightarrow (F - 32) \times \frac{5}{9}$. Output as float `%.1f`.
     * `v6`: Output as float `%.1f`.
     * `v7`–`v12`: Output as general float `f"{val:g}"`.
     * `b1`: `kw` / `kilowatt(s)` $\rightarrow \times 1000$. Output as rounded integer (`int(round(val))`).
     * `b2`: Output as general float `f"{val:g}"`.
     * `b3` / `b4` / `b5`: `kwh` $\rightarrow \times 1000$, `mwh` $\rightarrow \times 10^6$. Output as rounded integer (`int(round(val))`).
     * `b6`: Parse integer (`int(float(state))`), validate range `0 <= val <= 9` (log warning and omit if out of range).
   * Log a warning if `b2`–`b6` are present without `b1` (since PVOutput requires `b1` when uploading battery data).
3. Append flags:
   * If `c1` is `True`: Append `&c1=1`.
   * If `n` is `True`: Append `&n=1`.
4. Log human-readable summary at `INFO` level.
5. POST payload with headers (`X-Pvoutput-Apikey`, `X-Pvoutput-SystemId`).

---

## 6. Implementation Roadmap & Running Checklist

- [x] **Step 1: Constants & Data Model**
  - Updated `custom_components/pvoutput_publisher/const.py` with `CONF_V1`..`CONF_V12`, `CONF_C1`, `CONF_NET`, `CONF_NOTES`.
- [x] **Step 2: Migration Engine**
  - Implemented `async_migrate_entry(hass, config_entry)` in `__init__.py`.
  - Implemented helper function `migrate_v1_system_to_v2(hass, system_data)`.
- [x] **Step 3: Configuration & Options Flow**
  - Updated `PVOutputPusherConfigFlow.VERSION = 2`.
  - Updated `_get_system_schema()` in `config_flow.py` for v2 fields and notes.
- [x] **Step 4: Push Pipeline in `__init__.py`**
  - Updated `push_data()` to process v2 system fields, flags, and notes.
- [x] **Step 5: Base English Translations (`en.json`)**
  - Added friendly labels and helper tooltips for v1..v12, c1, net, and notes in `en.json`.
- [x] **Step 6: Unit & Integration Tests**
  - Added unit tests for `async_migrate_entry` (live state present, registry lookup, fallback naming, idempotency, duplicate sensors, secondary-only configs, consumption lifetime).
  - Updated config flow tests for v2 schema and full field editing.
  - Added specific regression tests for temperature sensors without `device_class: temperature`.
  - Updated push payload tests for v2 parameters, flags, unit conversions, and notes exclusion.
  - Test suite passing with 24/24 tests (95% coverage).
- [x] **Step 7: Documentation (`README.md`, `CHANGELOG.md`)**
  - Updated `README.md` to document the V2 parameter mapping, notes field, and migration.
  - Updated `CHANGELOG.md` with 2.0.0 release notes.
- [x] **Step 8: Multi-Language Translations (Final Phase)**
  - Generated updated translations for `de.json`, `es.json`, `ja.json`, `zh-Hans.json`, `zh-Hant.json` matching `en.json`.

---

## 7. Discoveries & Implementation Notes
*(Updated dynamically during implementation)*
- *2026-10-11:* Switched from dual-mode toggle to unified v2 architecture with automated `async_migrate_entry` to provide cleaner UX and zero configuration ambiguity.
- *2026-10-11:* English translation (`en.json`) updated first; other language files deferred to final phase per iterative development plan.
- *2026-10-11:* Migration logic defaults `c1=True` for migrated Energy generation sensors because Home Assistant's Entity Registry does not persist `state_class` to disk at boot time. This ensures lifetime energy sensors display `[x] Cumulative Energy Flag` in the UI and prevent PVOutput 400 Bad Request errors.
- *2026-10-11:* Migration logic refined to prevent duplicate sensor assignments (e.g. if a user configured two energy sensors in v1, secondary energy is safely ignored rather than mistakenly placed into `v2` Power).
- *2026-11-16 (v2.1.0):* Added battery parameters (`b1`–`b6`) and reorganized `v7`–`v12` and `b1`–`b6` into a collapsible `donation_fields` section in the config/options UI.
- *2026-11-16 (v2.1.0):* Switched optional fields in `_get_system_schema` from `default` to `suggested_value` and stripped empty strings in `_clean_system_input` so users can clear optional fields when editing a system.
- *2026-11-16 (v2.1.0):* Added orphaned status sensor cleanup in `sensor.py` when a system is removed or its `system_id` changes, and expanded `v7`–`v12`, `b3`, and `b6` selectors to support `sensor`, `number`, and `input_number` entities.

