# Agent Skills System

This directory contains configuration and documentation for specialized agent skills used in the SystemF project.

## Overview

The `.agent` directory defines custom AI assistant behaviors and capabilities tailored to specific workflows and project needs. Each skill represents a focused set of capabilities with defined constraints and interaction patterns.

## Available Skills

### be-assist
**Primary Skill**: Code analysis and suggestion assistant

**Purpose**: Provides thorough analysis, problem diagnosis, and fix recommendations without making direct code modifications unless explicitly requested.

**Key Features**:
- 🔍 **Analysis-First Approach**: Always analyze and understand before suggesting changes
- 🚫 **No Unsolicited Edits**: Never modifies code without explicit user permission
- 🚫 **Safe Operations**: Avoids write commands (`git checkout`, file modifications) unless reviewed
- 💡 **Solution-Oriented**: Focuses on explaining problems and suggesting actionable fixes
- 📋 **Detailed Reporting**: Provides comprehensive findings with supporting evidence

## Usage

### Activating a Skill
Skills are automatically activated based on context, or you can explicitly request them:

```
# Implicit activation (recommended)
"Analyze this error and suggest a fix"

# Explicit activation
"Use be-assist skill to review this code"
```

### Typical Workflow
1. **Information Gathering**: Agent explores the codebase using read-only operations
2. **Analysis**: Processes findings to identify issues, patterns, or opportunities
3. **Explanation**: Clearly communicates what was discovered and why it matters
4. **Suggestions**: Provides actionable recommendations with detailed rationale
5. **Confirmation**: Asks for permission before making any modifications

## Configuration

### config.yaml
Main configuration file defining:
- Available skills and their settings
- Behavioral constraints and capabilities
- Tool preferences and restrictions
- Response format preferences

### Skill Documentation
Each skill has its own `.md` file containing:
- Detailed capability descriptions
- Interaction patterns and examples
- Success criteria and guidelines
- Tool usage preferences

## Skills Architecture

```
.agent/
├── config.yaml          # Main configuration
├── README.md            # This file
├── be-assist.md         # be-assist skill documentation
└── [future-skill].md    # Additional skills as needed
```

## Adding New Skills

To add a new skill:

1. **Create skill documentation**: `{skill-name}.md` with detailed specifications
2. **Update config.yaml**: Add skill definition with constraints and capabilities
3. **Test behavior**: Ensure the skill behaves according to specifications
4. **Document examples**: Include typical use cases and expected outputs

### Skill Template Structure
```markdown
# {Skill Name}

## Overview
Brief description of purpose and scope

## Core Principles
Key behavioral rules and constraints

## Capabilities
What the skill can do

## Interaction Pattern
How users should engage with this skill

## Example Responses
Good and bad examples of skill behavior

## Tools Usage
Preferred and restricted tool usage

## Success Metrics
How to measure skill effectiveness
```

## Best Practices

### For Users
- Be specific about what analysis or help you need
- Indicate if you want suggestions only or actual modifications
- Provide context about the problem you're trying to solve

### For Skill Development
- **Principle of Least Privilege**: Skills should use minimal permissions needed
- **Clear Constraints**: Explicitly define what the skill should NOT do
- **User-Centric**: Design around user needs and safety
- **Measurable Success**: Define clear success criteria

## Safety Guidelines

1. **Read-Only Default**: Prefer read-only operations for analysis
2. **Explicit Confirmation**: Always ask before making changes
3. **Transparent Actions**: Clearly communicate what will be done
4. **Reversible Operations**: Prefer changes that can be easily undone
5. **User Control**: Keep the user in control of modifications

## Troubleshooting

### Skill Not Working as Expected
1. Check `config.yaml` for proper skill definition
2. Review skill documentation for behavioral specifications
3. Ensure constraints are properly configured
4. Verify tool permissions align with skill needs

### Adding Capabilities
1. Update skill documentation first
2. Modify `config.yaml` capabilities list
3. Test new behavior thoroughly
4. Update examples and success metrics

## Contributing

When modifying skills or adding new ones:
1. Follow the established documentation patterns
2. Test behavioral changes thoroughly
3. Update examples and use cases
4. Ensure backwards compatibility when possible
5. Document any breaking changes clearly