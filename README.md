# Home Assistant PVOutput Publisher

A custom Home Assistant integration that actively pushes your solar generation, home consumption, and local temperature data directly to [PVOutput.org](https://pvoutput.org/).

Unlike the official Home Assistant PVOutput integration (which only *downloads* data), this integration acts as an automated publisher, bridging your local Home Assistant sensors to your public PVOutput dashboard.

## Disclaimer: AI-Generated Project
Please note that the code and documentation for this project were primarily generated with the assistance of an AI. While it has been actively tested and confirmed to work perfectly within Home Assistant, it is provided "as is." Please review the code and use it at your own discretion.

---

## Features
* **UI Config Flow:** Fully configurable via the Home Assistant UI. No YAML required.
* **Multi-System Support:** Publish data for multiple solar arrays or inverters to different PVOutput System IDs using a single API key.
* **Strict Clock Alignment:** Synchronizes uploads to exact wall-clock intervals (e.g., :00, :05, :10) to prevent data drift and match PVOutput's native 5-minute buckets perfectly, even after Home Assistant restarts.
* **Smart Data Detection:** Automatically formats the payload based on the units of your selected sensors (Watts vs. Watt-hours, Celsius vs. Fahrenheit).
* **Maximum Accuracy Dual-Sensors:** Support for selecting both Power and Energy sensors simultaneously to plot the most accurate live power curves without relying on backend estimation.
* **Lifetime Energy Support:** Automatically detects `state_class: total` sensors and flags PVOutput to calculate your daily yield for you.
* **Comprehensive Metrics:** Supports pushing Generation, Consumption, and Temperature data simultaneously.
* **Last Upload Sensor:** Creates a timestamp entity in Home Assistant so you can monitor exactly when the last successful push occurred.
* **Multi-Language Support:** Fully translated into English, Japanese, Spanish, German, and Chinese (Simplified & Traditional).

---

## Smart Sensor Detection
PVOutput requires data to be formatted precisely. This integration looks at the `unit_of_measurement` and `state_class` of your selected sensors and automatically handles the conversions:

### Generation & Consumption
* **Single Sensor (Smart Detection):** You can select a single Power (W) or Energy (Wh) sensor. The integration will upload it, and PVOutput will automatically estimate the missing metric.
* **Dual Sensors (Maximum Accuracy):** For the best results, select BOTH a Power and an Energy sensor in the UI configuration. The integration will automatically detect which is which and upload them simultaneously, providing exact live output and daily totals without requiring PVOutput to do any mathematical guessing.
* **Lifetime Energy:** If your sensor tracks lifetime yield (e.g., `state_class: total_increasing`), the integration sends the `&c1=1` flag.

### Temperature
* If your Home Assistant sensor uses Fahrenheit (`°F`), it will automatically be converted to Celsius before uploading, as PVOutput strictly requires Celsius for its `v5` parameter.

---

## Installation

This integration is installed via [HACS](https://hacs.xyz/).

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations**.
3. Click the three dots in the top right corner and select **Custom repositories**.
4. Paste the URL of this GitHub repository `https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher`
5. Select **Integration** as the Category and click **Add**.
6. Search for **PVOutput Publisher** in HACS and click **Download**.
7. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **PVOutput Publisher**.
4. Enter your global **PVOutput API Key** (found in your PVOutput account settings).
5. Add your first system by providing:
   * **System Name:** A friendly name for your reference.
   * **System ID:** Your PVOutput System ID.
   * **Primary Solar Sensor:** Your inverter's power (W) or energy (Wh) sensor.
   * **Secondary Solar Sensor:** (Optional) If you selected a Power (W) sensor above, select your Energy (Wh) sensor here, or vice versa, for maximum accuracy. If you only provide the primary sensor, PVOutput will automatically estimate the missing value, which may result in less accurate data. 
   * **Consumption Sensor:** (Optional) Your home's power draw or energy usage sensor.
   * **Temperature Sensor:** (Optional) Outside temperature.
   * **Update Frequency:** How often to push data to PVOutput (5 to 180 minutes).

### Managing Multiple Systems
You can add, edit, or remove systems at any time. Simply go to **Settings > Devices & Services**, find the **PVOutput Publisher** integration card, and click **Configure**.

---

## Entities Created
For every system you configure, this integration creates a sensor:
* `sensor.pvoutput_[system_name]_last_upload`

This sensor tracks the exact date and time of the last successful HTTP 200 OK response from the PVOutput API. You can use this sensor in your Lovelace dashboards or to trigger automations (e.g., send a notification if data hasn't successfully published in over an hour).

---

## Troubleshooting & Logs
If data is not appearing in PVOutput, check your Home Assistant logs (**Settings > System > Logs**). The integration gracefully handles network drops, but will print detailed error messages if the PVOutput API rejects your payload (e.g., invalid API key, incorrect System ID, or pushing data too far in the past). You can view the raw outbound payload by setting the logging level for `custom_components.pvoutput_publisher` to `info` in your `configuration.yaml`.

```yaml
## Logging
logger:
  default: warning
  logs:
    custom_components.pvoutput_publisher: debug
```
