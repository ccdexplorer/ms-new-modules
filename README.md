## Micro Service Modules

The goal of this service is to process module information and store this on the `modules` collections. 

### Trigger(s)
As with all micro services, also this service is subscribed to topics from the MQTT broker. Specifically, this service is subscribed to the topic `ccdexplorer/+/heartbeat/module/new`. The `heartbeat` process publishes to this topic when a new module in deployed (transaction type: `account_transaction.module_deployed`).
The message that gets published contains the `module_ref` for the deployed module. 
On receiving the trigger,  the following happens:
1. Module Pocess
2. Module Verification


#### Module Process
The module processing involves several steps to ensure the module is correctly parsed and stored in the relevant collection. The steps include:
1. **Fetching Module Data**: Retrieve the module data from the node using the `module_ref`.
2. **Data Transformation**: Transform the module data into the required format for storage and further processing.
3. **Storing Module Data**: Store the transformed module data into the `modules` collection in the database.
4. **Logging**: Log the processing steps and any issues encountered for auditing and debugging purposes.

#### **Module Verification**
The module verification tries to establish whether the module can be verified. The verification steps include:
1. **Determines the appropriate database** to use based on the network (mainnet or testnet).
2. **Saves the module** using the Concordium client, with command `concordium-client module show {module_ref} --out {module_ref}.out`
3. **Runs a subprocess** to print the build information of the module, with command `cargo concordium print-build-info --module {module_ref}.out`.
4. **Parses the build information** to extract the build image, build command, and archive hash.
5. **Checks if the source code link** is present in the build information.
6. If the source code link is present, **retrieves the source code** from the link and saves it to disk.
7. **Extracts the source code** at `/src/lib.rs` and verifies it against the module with command `cargo concordium verify-build --module {path/to/saved/source_code}`. This command spins up a Docker container in the background as specified in the property `build_image_used`.
8. **Saves and sends the verification result**.

