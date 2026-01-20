
## Product Requirement: Device Discovery and Load-Balanced Detail Retrieval

### Background

The system integrates **net4home bus devices** into **Home Assistant**.
Devices connected to the net4home bus are able to announce their presence using a discovery mechanism.
Home Assistant must detect these devices, register them, and later retrieve their detailed capabilities and configuration.

A key challenge is that **immediately querying all discovered devices for full details would create excessive load on the net4home bus**, potentially leading to communication issues or unreliable behavior.

---

## Objective

Design a **robust, balanced, and scalable strategy** to:

1. Discover new net4home devices reliably
2. Register them in Home Assistant with minimal initial data
3. Retrieve detailed device information **gradually**, in a controlled and load-balanced manner

---

## Discovery Strategy Overview

### Step 1: Bus-Wide Discovery

* Home Assistant sends a `D0_ENUM_ALL` command on the net4home bus.
* This command prompts all connected modules to announce themselves.

### Step 2: Initial Device Registration

* Each module responds with **basic identification information** (e.g. address, module type, minimal metadata).
* Based on this response:

  * Home Assistant creates a corresponding **device entry**.
  * At this stage, the device is considered *known* but *not fully described*.

> At this point, Home Assistant does **not** yet have detailed information such as:
>
> * Supported functions
> * Channels
> * Sensors / actuators
> * Capabilities or configuration options

---

## Problem Statement: Bus Load

* Immediately querying all newly discovered devices for full details would:

  * Generate a burst of bus traffic
  * Increase latency
  * Risk packet loss or bus congestion
* This is especially problematic in installations with many modules.

---

## Required Solution: Load-Balanced Detail Retrieval

Home Assistant must implement a **deferred and distributed polling strategy** for device detail retrieval.

### Core Requirements

* Device detail queries must **not** be executed immediately after discovery.
* Queries must be **spread over time** to avoid peak load.
* The strategy must be:

  * Predictable
  * Configurable
  * Resilient to interruptions (e.g. restart of Home Assistant)

---

## Proposed Strategy Characteristics

A good and balanced strategy should include:

### 1. Deferred Detail Fetching

* After initial discovery, devices are placed into a **pending detail state**.
* Detailed queries are executed only after a delay.

### 2. Rate Limiting

* Only a limited number of devices may be queried within a defined time window.
* Example:

  * One device every *N* seconds
  * Or a small batch with pauses in between

### 3. Sequential or Priority-Based Processing

* Devices are queried **one after another**, or
* Based on priority rules (e.g. device type, user interaction, critical devices first)

### 4. Persistence

* The system must remember which devices:

  * Are fully initialized
  * Are pending detail retrieval
* This state must survive restarts of Home Assistant.

---

## Expected Outcome

* All net4home devices are reliably discovered and registered.
* Bus load remains stable and predictable.
* Full device information is eventually available in Home Assistant without impacting bus stability.
* The solution scales well from small to large installations.

---

## Non-Goals

* Real-time full device initialization immediately after discovery
* Optimization of the net4home protocol itself

