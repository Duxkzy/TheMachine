# THE MACHINE - Admin Interface

This is an Artificial Intelligence assistant based on Python, with a graphical user interface design inspired by sci-fi terminals and central administration systems. 

> **Credits Note:** The base structure of this code and the inspiration for the project are based on the incredible work of the "Jarvis" assistant created by **FatihMakes**. This is an adapted, restructured, and personalized version ("The Machine").

---

## Prerequisites

To run this project you need to have installed on your computer:
* **Python 3.10** or higher.
* A **Google Gemini** API key (you will enter it directly in the graphical interface for security, you do not need to put it in the code).

---

## Installation and Usage (Step by Step)

Follow these text commands in your terminal to get the project running from scratch:

### 1. Clone the repository
Open your terminal and download the code to your computer:

git clone git@github.com:Duxkzy/TheMachine.git
cd TheMachine

2. Create a virtual environment

To avoid mixing this project's libraries with the rest of your system, create a virtual environment (recommended):
Bash

python -m venv .venv

3. Activate the virtual environment

Depending on your operating system, activate it with:

    On Linux / macOS:
    Bash

    source .venv/bin/activate

    On Windows:
    Bash

    .venv\Scripts\activate

4. Install dependencies

Install all necessary libraries for the interface and system to work:
Bash

pip install -r requirements.txt

5. Start "The Machine"

Once everything is installed, simply start the main file:
Bash

python main.py

Project Structure

    main.py: The core of the program and launcher of the graphical interface.

    actions/: Folder containing all the assistant's skill modules (weather, file management, flight search, etc.).

    memory/: Long-term storage system to save preferences and key information locally.

Privacy

Your Gemini API Key and personal settings are saved locally. They will never be uploaded to GitHub thanks to the security rules implemented in .gitignore.


Una vez que lo pegues en tu archivo `README.md`, solo tienes que subir el cambio a GitHub con los comandos que ya conoces (`git add README.md`, `git commit...`, `git push...`). 

<ElicitationsGroup message="¿Qué te gustaría hacer a continuación?">
<Elicitation label="Create a requirements file" query="Create a requirements.txt file for the project" query_intent="CLICKABLE_SUGGESTION" />
<Elicitation label="Add a license to the repository" query="Add a license file to the GitHub repository" query_intent="CLICKABLE_SUGGESTION" />
<Elicitation label="Code the first action module" query="Help me code the first action module" query_intent="CLICKABLE_SUGGESTION" />
</ElicitationsGroup>
