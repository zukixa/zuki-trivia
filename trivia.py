import discord
import asyncio
import json
import aiassist
from discord.ext import commands
from collections import deque
from discord.ext import commands, tasks
from discord import app_commands
import time


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        #    # This copies the global commands over to your guild.
        #    for guild in self.guilds:
        #        print(guild.id)
        #        print(guild.name)
        # MY_GUILD = discord.Object(id=1090022628946886726)
        # self.tree.copy_global_to(guild=MY_GUILD)
        # await self.tree.sync(guild=MY_GUILD)
        await self.tree.sync()


if __name__ == "__main__":
    intents = discord.Intents.all()
    client = MyClient(intents=intents)

with open("config.json", "r") as f:
    config = json.load(f)


def close_enough(response, answers):
    # Implement this function to evaluate if the user's response is close enough to the correct answer
    # You can use string similarity measures like Levenshtein distances or any other relevant algorithms
    # Check if response matches any of the answers
    for answer in answers:
        if response.lower() == answer.lower():
            return True

    return False


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
            'Hi ChatGPT. You are now a Trivia Generator that can only respond in json format. You will be given a topic, and you must respond with a trivia question, and list all possible answers in a json format. ((YOU CAN **ONLY** TALK IN ***JSON***)). For example, for the topic "Capitals", you would respond {"question": "What is the capital of France?", "answers": "Paris, PARIS, paris"} with all the answers being all possible valid answers to the question. ONLY RESPOND WITH ONE JSON RESPONSE. THAT IS ALL YOU ARE SUPPOSED TO RESPOND WITH. YOU WILL DIE IF YOU SAY ANYTHING ELSE EXCEPT THE JSON RESPONSE. BEGIN YOUR RESPONSE WITH "{". Your first topic is :'
            + topic
            + ". With the difficulty of the question being: "
            + difficulty
        )

        if asked_questions:
            prompt += "\n\nAlready asked questions:\n" + "\n".join(asked_questions)

        # AI-generated question fetching
        response = await aiassist.get_value(prompt)
        response = response.replace("\\n", "").replace('\\"', '"')
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

            user_response = await client.wait_for(
                "message",
                check=lambda m: (m.channel == interaction.channel and not m.author.bot),
                timeout=10,
            )

            if close_enough(user_response.content, answers):
                user_scores[user_response.author] = (
                    user_scores.get(user_response.author, 0) + 1
                )
                asked += 1
                await interaction.channel.send("Correct!")
                break  # Break out of the inner loop, so a new question will be fetched
            else:
                await interaction.channel.send("Incorrect!")

        if attempt == attempts:
            await interaction.channel.send(
                "Time's up!\nThe expected answers were: " + ",".join(answers)
            )
            break

    time_tracker.cancel()

    return user_scores, time_spent["seconds"]


@client.tree.command(
    name="quiz", description="Start a quiz on a given topic and difficulty."
)
async def _quiz(interaction: discord.Interaction, topic: str, difficulty: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    # Start the quiz
    user_scores, time_spent = await quiz(interaction, topic, difficulty)

    # Save the results
    with open("trivia_stats.json", "r+") as f:
        stats = json.load(f)
        if user_id not in stats:
            stats[user_id] = []
        stats[user_id].append(
            {"scores": user_scores, "time_spent": time_spent}
        )  # Store the user's scores
        f.seek(0)
        json.dump(stats, f, indent=4)
        f.truncate()

    # Send the result as a message
    result_message = "Quiz over! Here are the scores:\n"
    for user, score in user_scores.items():
        result_message += f"<@{user}>: {score} points\n"
    await interaction.channel.send(result_message)


@client.tree.command(name="stats", description="Show your quiz stats.")
async def _stats(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    embed = discord.Embed(title="Quiz Stats", color=0x1ABC9C)

    with open("trivia_stats.json", "r") as f:
        stats = json.load(f)

    if user_id not in stats:
        embed.description = "You haven't played a quiz yet!"
    else:
        total_points = sum([quiz_run["points"] for quiz_run in stats[user_id]])
        total_time = sum([quiz_run["time_spent"] for quiz_run in stats[user_id]])
        num_quizzes = len(stats[user_id])
        embed.description = (
            f"Quizzes Played: {num_quizzes}\n"
            f"Total Points: {total_points}\n"
            f"Total Time Spent: {total_time}s"
        )

    # Send the embed
    await interaction.followup.send(embed=embed)


client.run(config["token"])
