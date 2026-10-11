# Home Assistant PVOutput Publisher

A custom Home Assistant integration that actively pushes your solar generation, home consumption, and local temperature data directly to [PVOutput.org](https://pvoutput.org/).

Unlike the official Home Assistant PVOutput integration (which only *downloads* data), this integration acts as an automated publisher, bridging your local Home Assistant sensors to your public PVOutput dashboard.

## Disclaimer: AI-Generated Project
Please note that the code and documentation for this project were primarily generated with the assistance of an AI. While it has been actively tested and confirmed to work within Home Assistant, it is provided "as is." Please review the code and use it at your own discretion.

---

## Features
* **UI Config Flow:** Fully configurable via the Home Assistant UI with 1-to-1 mappings to PVOutput API parameters. Free options are presented first, with donation features organized in a smart collapsible section. No YAML required.
* **Internal System Notes:** Save private reference notes for each solar array in the Home Assistant UI without sending them to the public API.
* **Multi-System Support:** Publish data for multiple solar arrays or inverters to different PVOutput System IDs using a single API key.
* **Strict Clock Alignment:** Synchronizes uploads to exact wall-clock intervals (e.g., :00, :05, :10) to prevent data drift and match PVOutput's native intervals, even across Home Assistant restarts.
* **Standard Parameters (Free Accounts):**
  * **v1 (Energy Generation):** Watt-hours (automatically converts `kWh` and `MWh`).
  * **v2 (Power Generation):** Watts (automatically converts `kW`).
  * **v3 (Energy Consumption):** Watt-hours (automatically converts `kWh` and `MWh`).
  * **v4 (Power Consumption):** Watts (automatically converts `kW`).
  * **v5 (Temperature):** Automatically converts Fahrenheit (`°F`) to Celsius (`°C`).
  * **v6 (Voltage):** Inverter / Line voltage.
  * **Cumulative Flag (`c1=1`):** Informs PVOutput that energy readings represent lifetime cumulative values.
  * **Net Flag (`n=1`):** Informs PVOutput that power readings represent net export.
* **Donation Features (PVOutput Donation Account Required):**
  > [!NOTE]
  > The following parameters require an active [PVOutput Donation Account](https://pvoutput.org/help/donation.html). PVOutput ignores these parameters on free accounts.
  * **v7 – v12 (Extended Data):** Custom user-defined metrics (Extended Values 1 to 6).
  * **b1 – b6 (Battery Parameters):**
    * **b1 (Battery Power):** Watts (automatically converts `kW`; positive = charge, negative = discharge; *mandatory when uploading any battery data*).
    * **b2 (State of Charge):** Percentage (0–100%).
    * **b3 (Usable Capacity):** Watt-hours (automatically converts `kWh` and `MWh`).
    * **b4 (Lifetime Charge):** Watt-hours (automatically converts `kWh` and `MWh`).
    * **b5 (Lifetime Discharge):** Watt-hours (automatically converts `kWh` and `MWh`).
    * **b6 (Battery State):** Numeric status code (0–9).
* **Last Upload Sensor:** Creates a timestamp entity in Home Assistant to monitor when the last successful push occurred.
* **Multi-Language Support:** Fully translated into English, Japanese, Spanish, German, and Chinese.

---

## Installation

This integration is installed via [HACS](https://hacs.xyz/).

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations**.
3. Click the three dots in the top right corner and select **Custom repositories**.
4. Paste the URL of this GitHub repository: `https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher`
5. Select **Integration** as the Category and click **Add**.
6. Search for **PVOutput Publisher** in HACS and click **Download**.
7. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **PVOutput Publisher**.
4. Enter your global **PVOutput API Key** (found in your PVOutput account settings).
5. Configure your solar array parameters:

### General & Standard Settings (Free Accounts)
* **System Name:** A friendly name for your reference.
* **System ID:** Your PVOutput System ID.
* **Update Frequency:** How often to push data (5 to 180 minutes).
* **Internal Notes:** (Optional) Private reference notes.
* **v1: Energy Generation (Wh):** (Optional) Generation energy sensor.
* **v2: Power Generation (W):** (Optional) Generation power sensor.
* **v3: Energy Consumption (Wh):** (Optional) Consumption energy sensor.
* **v4: Power Consumption (W):** (Optional) Consumption power sensor.
* **v5: Temperature:** (Optional) Outside temperature sensor.
* **v6: Voltage:** (Optional) Inverter/grid line voltage.
* **Cumulative Flag (`c1=1`):** Check if energy sensors supply lifetime counter values.
* **Net Power Flag (`n=1`):** Check if power readings represent net export.

### Donation Features (PVOutput Donation Required)
*Expand the **Donation Features** section in the UI to configure:*
* **v7 – v12: Extended Data:** (Optional) Custom donation metrics.
* **b1: Battery Power (W):** (Optional) Instantaneous battery power (positive for charge, negative for discharge).
* **b2: Battery State of Charge (%):** (Optional) Battery charge percentage (0–100%).
* **b3: Battery Usable Capacity (Wh):** (Optional) Usable battery capacity.
* **b4: Battery Lifetime Charge (Wh):** (Optional) Cumulative lifetime battery charge energy.
* **b5: Battery Lifetime Discharge (Wh):** (Optional) Cumulative lifetime battery discharge energy.
* **b6: Battery State (Code 0-9):** (Optional) Numeric battery status code.

### Managing Multiple Systems
You can add, edit, or remove systems at any time. Simply go to **Settings > Devices & Services**, find the **PVOutput Publisher** integration card, and click **Configure**.

---

## Entities Created
For every system you configure, this integration creates a sensor:
* `sensor.pvoutput_[system_name]_last_upload`

This sensor tracks the exact date and time of the last successful HTTP 200 OK response from the PVOutput API. You can use this sensor in your Lovelace dashboards or to trigger automations (e.g., alert if data hasn't published in over an hour).

---

## Troubleshooting & Logs
If data is not appearing in PVOutput, check your Home Assistant logs (**Settings > System > Logs**). The integration will log the exact formatted outbound metrics at the `INFO` level:

```yaml
## Logging
logger:
  default: warning
  logs:
    custom_components.pvoutput_publisher: info
```
