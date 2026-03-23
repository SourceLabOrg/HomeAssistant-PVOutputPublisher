# Home Assistant PVOutput Publisher

A custom Home Assistant integration that pushes your live solar generation or daily cumulative energy data directly to [PVOutput.org](https://pvoutput.org/).

Unlike the official Home Assistant PVOutput integration (which only *downloads* data), this integration actively *publishes* your local Home Assistant sensor data up to your PVOutput account.

## Disclaimer: AI-Generated Project
Please note that the code and documentation for this project were primarily generated with the assistance of an AI. While it has been actively tested and confirmed to work within Home Assistant, it is provided "as is." Please review the code and use it at your own discretion.

---

## Features
* **UI Config Flow:** Fully configurable via the Home Assistant UI. No YAML required!
* **Multi-System Support:** Publish data for multiple solar arrays or inverters to different PVOutput System IDs using a single API key.
* **Customizable Frequency:** Choose how often to publish data (5, 10, 15, 30, 60, or 180 minutes).
* **Smart Power vs. Energy Detection:** Automatically formats the payload based on the sensor you select (see below).
* **Last Upload Sensor:** Creates a timestamp entity in Home Assistant so you can monitor exactly when the last successful push occurred.

---

## Smart Sensor Detection (Power vs. Energy)
PVOutput expects data in one of two formats. This integration looks at the `unit_of_measurement` of your selected sensor and automatically sends the correct data type:

### 1. Instantaneous Power (Watts / kW)
If you select a sensor measuring **Watts** or **kW** (e.g., current live generation), the integration automatically converts it to pure Watts and sends it to PVOutput as the `v2` (Power Generation) parameter.
* *Best for 5-minute update frequencies.*

### 2. Cumulative Energy (Wh / kWh)
If you select a sensor measuring **Wh** or **kWh** (e.g., "Daily Solar Energy"), the integration converts it to pure Watt-hours and sends it as the `v1` (Energy Generation) parameter. PVOutput will automatically calculate the average power for the interval based on the change in energy.
* *Best for longer update frequencies (30+ minutes) to ensure you don't miss generation data if clouds pass over between updates.*

---

## Installation

This integration is installed via [HACS](https://hacs.xyz/).

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations**.
3. Click the three dots in the top right corner and select **Custom repositories**.
4. Paste the URL of this GitHub repository.
5. Select **Integration** as the Category and click **Add**.
6. Search for **PVOutput Publisher** in HACS and click **Download**.
7. **Restart Home Assistant**.
8. *(Important)* Hard-refresh your browser to clear the frontend cache.

---

## Configuration

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **PVOutput Publisher**.
4. Enter your global **PVOutput API Key** (found in your PVOutput account settings).
5. Add your first system by providing:
    * **System Name:** A friendly name for your reference.
    * **System ID:** Your PVOutput System ID.
    * **Solar Sensor Entity:** The Home Assistant sensor tracking your solar generation.
    * **Update Frequency:** How often to push data to PVOutput.

### Managing Multiple Systems
You can add, edit, or remove systems at any time. Simply go to **Settings > Devices & Services**, find the **PVOutput Publisher** integration card, and click **Configure**.

---

## Entities Created
For every system you configure, this integration creates a sensor:
* `sensor.pvoutput_[system_name]_last_upload`

This sensor tracks the exact date and time of the last successful HTTP 200 OK response from the PVOutput API. You can use this sensor in your Lovelace dashboards or to trigger automations (e.g., send a notification if data hasn't successfully published in over an hour).

---

## Troubleshooting & Logs
If data is not appearing in PVOutput, check your Home Assistant logs (**Settings > System > Logs**). The integration will gracefully handle network drops, but will print detailed error messages if the PVOutput API rejects your payload (e.g., invalid API key, incorrect System ID, or pushing data too far in the past).
