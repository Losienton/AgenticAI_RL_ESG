# AgenticAI_RL_ESG

Energy Saving Green (ESG) networking project using Reinforcement Learning and heuristic algorithms to optimize link sleeping in a simulated TANET backbone network.

## Overview

This project implements an SDN-based energy saving system for a 17-node / 33-link ISP backbone topology running ISIS-SR + MPLS on Cisco XRv routers in EVE-NG. An RL agent (PPO) and a 9-step heuristic algorithm decide which links to shut down during low-traffic periods, with OpenDaylight (ODL) RESTCONF executing the changes.

## Architecture

- **Backend** (`esgbackend/`): FastAPI server handling telemetry collection, RL inference, heuristic decisions, and RESTCONF command generation
- **Frontend** (`esgdemo/`): React web UI for visualization and control
- **Evaluation** (`evaluation/`): Scenario-based evaluation scripts comparing RL, heuristic, and greedy strategies
- **Router Configs** (`original_configs/`, `current_configs/`): Cisco XRv configuration files for the 17-node topology

## Tech Stack

- Python, FastAPI, Stable Baselines3 (PPO), PyTorch
- React, JavaScript
- Cisco XRv (IOS-XR), ISIS-SR, MPLS
- OpenDaylight (ODL) RESTCONF
- EVE-NG network emulation
