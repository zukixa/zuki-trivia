import Levenshtein
import discord
import asyncio
import typing
import json
import httpx
import aiassist
from discord.ext import commands
from collections import deque
from discord.ext import commands, tasks
from discord import app_commands
import time
from asyncio import sleep


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


def close_enough(response, answers):
    threshold = 2
    # Implement this function to evaluate if the user's response is close enough to the correct answer
    # You can use string similarity measures like Levenshtein distances or any other relevant algorithms
    # Check if response matches any of the answers
    response = response.lower()
    for answer in answers:
        answer = answer.lower()

        # Check if the response is an exact match
        if response == answer:
            return True

        # Calculate the Levenshtein distance
        distance = Levenshtein.distance(response, answer)

        # Check if the distance is within the threshold
        if distance <= threshold:
            return True

    return False


async def get_aiassist_value(prompt):
    while True:
        try:
            response = await aiassist.get_value(prompt)
            return response
        except httpx.ReadTimeout:
            await sleep(5)  # Wait for 5 seconds before trying again


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
        response = await get_aiassist_value(prompt)
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

            try:
                user_response = await client.wait_for(
                    "message",
                    check=lambda m: (
                        m.channel == interaction.channel and not m.author.bot
                    ),
                    timeout=30,
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
    with open("trivia_stats.json", "r") as f:
        stats = json.load(f)
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


client.run(config["token"])
