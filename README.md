# Missing Contract Slack Bot

A Slack bot that monitors a channel for contract review requests, automatically summarizes the attached contract using an LLM, and creates a GitHub issue for legal teams to track.

---

## Features

- Listens for `@legal-bot please review` mentions with file attachments  
- Downloads and parses contract files  
- Generates concise contract summaries via OpenAI's GPT models  
- Posts summary cards back to Slack  
- Opens a tracking issue on GitHub with the summary and file link  

---

## Prerequisites

- Python 3.8+ installed  
- A Slack workspace where you have permissions to install apps  
- A GitHub repository to store created issues  
- OpenAI API access  

---

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/ChiefVishPat/missing-contract-legal-bot.git
   cd missing-contract-legal-bot
   ```


2. **Create a virtual environment**
    ```bash
    python3 -m venv venv-missing-contract-bot
    source venv-missing-contract-bot/bin/activate
    ```

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    
4. **Environment Variables**
    Copy `.env.example` to `.env` and fill in the values:

    ```dotenv
    SLACK_BOT_TOKEN=your-slack-bot-token
    SLACK_SIGNING_SECRET=your-slack-signing-secret
    OPENAI_API_KEY=your-openai-api-key
    GITHUB_TOKEN=your-github-personal-access-token
    GITHUB_REPO=owner/repo-name
    ```

## Usage

1. **Run the bot**
    ```bash
    source venv-missing-contract-bot/bin/activate
    python app.py
    ```

2. **Interact in Slack**
    - Invite @legal-bot to a channel:
    `/invite @legal-bot`

    - Upload a contract file and post:
    `@legal-bot please review`
    You should see a summary card in Slack and a new GitHub issue created.

## Development
- The bot entrypoint is app.py.

- Uses slack-bolt for Slack event handling and openai for summaries.

- GitHub integration via REST API calls in create_github_issue.

- Feel free to extend with additional event handlers, storage layers, or alternate ticketing systems.

## License
This project is licensed under the MIT License. See LICENSE for details.