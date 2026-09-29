# Module 4: Agent Groups & Assignment Specification

## Web UI Location
- **Create Groups**: **Agents & Groups** > **Create Agent Groups**
- **Assign Agents**: **Agents & Groups** > **Assign Agents**

## Sub-feature A: Create Agent Groups
Takes a simple list of group names, one per line.

```text
Tier 1 Customer Service
Tier 2 Technical Support
VIP Care Group
Billing Support Group
Distributor Technical Support
```

## Sub-feature B: Assign Agents to Groups
Maps agent emails to their respective target groups in CSV format.

### Columns
`email, group_name`

### Demonstration Output

```csv
email, group_name
agent.one@example.com, Tier 1 Customer Service
agent.two@example.com, Tier 2 Technical Support
vip.specialist@example.com, VIP Care Group
tech.lead@example.com, Distributor Technical Support
```
