import Levenshtein, discord, asyncio, typing, json, aiohttp, aiofiles
from discord import app_commands
from openai import AsyncOpenAI
from curl_cffi.requests import AsyncSession

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


if __name__ == "__main__":
    intents = discord.Intents.all()
    client = MyClient(intents=intents)

with open("config.json", "r") as f:
    config = json.load(f)
    apikey = config['zj-api-key']

oai = AsyncOpenAI(base_url="https://zukijourney.xyzbot.net/v1",api_key=apikey)

def remove_newlines(s):
    return s.replace('\n', ' [newline] ').replace('\r', '').replace("<", "[").replace(">", "]").replace("(","[").replace(")","]").replace("{", "[").replace("}", "]").replace('"', " [apostrophe] ").replace("'", " [apostrophe] ")

def generate_random_string(length=11):
    characters = string.ascii_lowercase + string.digits
    session_hash = ''.join(random.choice(characters) for _ in range(length))
    return session_hash


async def close_enough(response, answers):
    threshold = 2
    # Check if response matches any of the answers
    response = response.lower()
    for answer in answers:
        answer = answer.lower().strip()

        # Check if the response is an exact match
        if response == answer:
            return True

        # Calculate the Levenshtein distance
        distance = Levenshtein.distance(response, answer)

        # Check if the distance is within the threshold
        if distance <= threshold:
            return True

    return False


async def handle_ai_request(prompt):
    try:
        prompt = remove_newlines(prompt)
        response = oai.chat.completions.create(
            messages=[{'role':'user','content':prompt}],
            model="llama-3.1-sonar-large-128k-online",
            stream=False,
        )
        return response.choices[0].message.content
    except:
        return None

@client.event
async def on_ready():
    print(f"Logged In as {client.user}")
    act = discord.Activity(name="trivia with you :>", type=discord.ActivityType.playing)
    await client.change_presence(status=discord.Status.idle, activity=act)


async def track_time(time_spent):
    while True:
        await asyncio.sleep(1)
        time_spent["seconds"] += 1


async def quiz(interaction, topic, difficulty):
    user_scores = {}
    time_spent = {"seconds": 0}
    time_tracker = asyncio.create_task(track_time(time_spent))
    asked_questions = []

    num_questions = 10
    asked = 0
    while asked < num_questions:
        # Move the question-fetching code into the inner loop
        prompt = (
            'Hi.\n You are now a Trivia Generator that can only respond in json format.\n You will be given a topic, and you must respond with a trivia question, and list all possible answers in a json format.\n ((YOU CAN **ONLY** TALK IN ***JSON***)).\n For example, for the topic "Capitals", you would respond {"question": "What is the capital of France?", "answers": "Paris, PARIS, paris"} with all the answers being all possible valid answers to the question.\n ONLY RESPOND WITH ONE JSON RESPONSE.\n THAT IS ALL YOU ARE SUPPOSED TO RESPOND WITH.\n YOU WILL DIE IF YOU SAY ANYTHING ELSE EXCEPT THE JSON RESPONSE.\n BEGIN YOUR RESPONSE WITH "{".\n\n Your first topic is: ((('
            + topic
            + "))).\n With the difficulty of the question being: ((("
            + difficulty + ")))" 
        )

        if asked_questions:
            prompt += (
                "\n\nThese are already asked questions, SO DO NOT ASK ANYTHING SIMILAR TO THESE QUESTIONS AGAIN. \nALL OF YOUR QUESTIONS MUST BE UNIQUE. \nDO NOT REPEAT QUESTIONS. \nALWAYS MAKE UP A NEW QUESTION. \nYOU WILL DIE IF YOU REPEAT A QUESTION.\nPrevious Questions:\n"
                + "\n".join(asked_questions)
            )
        # AI-generated question fetching
        response = await handle_ai_request(prompt)
        if not response:
            await interaction.followup.send('Free AI provider failed to respond. Quiz cancelled.')
            return
        response_dict = json.loads(response)
        question = response_dict["question"]
        answers = response_dict["answers"]
        if isinstance(answers, str):
            answers = answers.split(", ")

        asked_questions.append(question)
        await interaction.channel.send(question)

        attempts = 3  # Maximum number of attempts per question
        attempt = 0

        while attempt < attempts:
            attempt += 1

            try:
                user_response = await client.wait_for(
                    "message",
                    check=lambda m: (
                        m.channel == interaction.channel and not m.author.bot
                    ),
                    timeout=30,
                )

                if (await close_enough(user_response.content, answers)):
                    user_scores[user_response.author] = (
                        user_scores.get(user_response.author, 0) + 1
                    )
                    asked += 1
                    await interaction.channel.send("Correct!")
                    break  # Break out of the inner loop, so a new question will be fetched
                else:
                    await interaction.channel.send("Incorrect!")

            except asyncio.TimeoutError:  # Handling TimeoutError
                await interaction.channel.send(
                    "Time's up!\nThe expected answers were: " + ",".join(answers)
                )
                break

        if attempt == attempts:
            await interaction.channel.send(
                "Time's up!\nThe expected answers were: " + ",".join(answers)
            )
            break

    time_tracker.cancel()
    user_scores_with_ids = {str(user.id): score for user, score in user_scores.items()}

    return user_scores_with_ids, time_spent["seconds"]


@client.tree.command(
    name="quiz", description="Start a quiz on a given topic and difficulty."
)
async def _quiz(interaction: discord.Interaction, topic: str, difficulty: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    # Start the quiz
    user_scores, time_spent = await quiz(interaction, topic, difficulty)

    # Save the results
    async with aiofiles.open("trivia_stats.json", mode="r+") as f:
        stats = json.loads(await f.read())
        if user_id not in stats:
            stats[user_id] = []
        stats[user_id].append(
            {"scores": user_scores, "time_spent": time_spent}
        )  # Store the user's scores
        await f.seek(0)
        await f.write(json.dumps(stats, indent=4))
        await f.truncate()

    # Send the result as a message
    result_message = "Quiz over! Here are the scores:\n"
    for user, score in user_scores.items():
        result_message += f"<@{user}>: {score} points\n"
    await interaction.channel.send(result_message)

@client.tree.command(name="help", description="Show detailed help for the Trivia bot")
async def show_help(interaction: discord.Interaction):
    await interaction.response.defer()

    help_embed = discord.Embed(
        title="Trivia Bot Help",
        description="Welcome to the Trivia Bot! Here's how to use the bot:",
        color=discord.Color.blue()
    )

    help_embed.add_field(
        name="Starting a Quiz",
        value="Use the `/quiz` command to start a new quiz:\n"
              "```/quiz topic: &lt;topic&gt; difficulty: &lt;difficulty&gt;```\n"
              "Replace `<topic>` with any subject you want to be quizzed on.\n"
              "Replace `<difficulty>` with easy, medium, or hard.",
        inline=False
    )

    help_embed.add_field(
        name="Quiz Rules",
        value="• Each quiz consists of 10 questions\n"
              "• You have 3 attempts per question\n"
              "• You have 30 seconds to answer each question\n"
              "• The bot uses AI to generate unique questions\n"
              "• Answers are checked for close matches",
        inline=False
    )

    help_embed.add_field(
        name="Viewing Stats",
        value="Use the `/stats` command to view your quiz statistics:\n"
              "```/stats [user: @mention]```\n"
              "You can optionally mention a user to see their stats.",
        inline=False
    )

    help_embed.add_field(
        name="Stats Information",
        value="The stats show:\n"
              "• Number of quizzes played\n"
              "• Total points earned\n"
              "• Total time spent on quizzes",
        inline=False
    )

    help_embed.set_footer(text="zuki.trivia- Test your knowledge and have fun!")

    await interaction.followup.send(embed=help_embed)

@client.tree.command(name="stats", description="Show your quiz stats.")
async def _stats(
    interaction: discord.Interaction, user: typing.Optional[discord.Member] = None
):
    await interaction.response.defer()
    if user:
        user_id = str(user.id)
        name = user.display_name
    else:
        user_id = str(interaction.user.id)
        name = interaction.user.display_name
    guild_id = str(interaction.guild.id)
    embed = discord.Embed(title=f"Quiz Stats for {name}", color=0x1ABC9C)
    async with aiofiles.open("trivia_stats.json", mode="r") as f:
        stats = json.loads(await f.read())
    print(stats)
    if guild_id not in stats:
        embed.description = "You haven't played a quiz yet!"
    else:
        guild_stats = stats[guild_id]
        total_points = 0
        total_time = 0
        num_quizzes = 0

        for quiz_run in guild_stats:
            if user_id in quiz_run["scores"]:
                total_points += quiz_run["scores"][user_id]
                total_time += quiz_run["time_spent"]
                num_quizzes += 1

        if num_quizzes == 0:
            embed.description = "You haven't played a quiz yet!"
        else:
            embed.description = (
                f"Quizzes Played: {num_quizzes}\n"
                f"Total Points: {total_points}\n"
                f"Total Time Spent: {total_time}s"
            )

    await interaction.followup.send(embed=embed)


client.run(config["triviatoken"])               
