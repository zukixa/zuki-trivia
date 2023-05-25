const { Client, Events, GatewayIntentBits, ActivityType } = require('discord.js');
const { generateQuiz } = require('country-quiz-generator');
const { token } = require('./config.json');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers,
    ],
});
// balls
const QUIZ_TYPES = {
    'whichCountryForGivenLanguage': 'Which one of these countries speaks {{answer}}?',
    'whichCountryForGivenFlag': 'Which country does this flag belong to?',
    'whichCountryForGivenCapital': '{{answer}} is the capital of which country?',
    'any': 'Randomized at random!'
};

client.once('ready', () => {
    console.log(`Ready! Logged in as ${client.user.tag}`);
    client.user.setPresence({ status: 'idle' });
    client.user.setActivity('trivia with you :>', { type: ActivityType.Playing });
});




client.on('messageCreate', async (message) => {
    if (message.author.bot || !message.content.startsWith('!quiz')) return;

    let quizType = message.content.split(' ')[1];
    if (typeof quizType === 'undefined') {
        quizType = 'any'
    }

    if (!QUIZ_TYPES[quizType]) {
        message.channel.send(
            `Invalid quiz type! Available quiz types: ${Object.keys(QUIZ_TYPES).join(
                ', '
            )}`
        );
        return;
    }
    let quiz
    if (quizType === 'any')
        quiz = generateQuiz(1)[0];
    else
        quiz = generateQuiz(1, quizType)[0];
    let answer = quiz.correctAnswer;
    let options = quiz.options.join(', ');
    let title
    if (quizType === 'any')
        title = quiz.title
    else
        title = quiz.title
    let quizMessage
    quizMessage = await message.channel.send(
        `**${title}**\n${options}`
    );
    const startTime = new Date();
    const scores = new Map();
    if (quiz.type === 'whichCountryForGivenFlag') {
        let flagSrcs = quiz.flagSrc.toString();
        let country_code = flagSrcs.split("/")[3].slice(0, 2);
        let flag = `https://flagsapi.com/${country_code.toUpperCase()}/flat/64.png`
        quizMessage2 = await message.channel.send(
            `${flag}`
        );
    }


    const filter = (m) =>
        (m.author.id === message.author.id && m.content.toLowerCase() === answer.toLowerCase()) || m.content === "!stop";

    const collector = message.channel.createMessageCollector({
        filter
    });

    collector.on('collect', async (m) => {
        if (m.content === "!stop") {
            const endTime = new Date();
            const duration = (endTime - startTime) / 1000;
            message.channel.send(`Quiz finished in ${duration} seconds.`);
            message.channel.send('Scores:');
            scores.forEach((score, userId) => {
                const user = message.guild.members.cache.get(userId).user;
                message.channel.send(`${user.username}: ${score}`);
            });
            collector.stop('Quiz Finished');
            return
        }
        await quizMessage.reply('Correct!');
        let userScore = scores.get(m.author.id) || 0;
        scores.set(m.author.id, userScore + 1)
        if (quizType === 'any') {
            quiz = generateQuiz(1)[0];
        }
        else
            quiz = generateQuiz(1, quizType)[0];
        answer = quiz.correctAnswer;
        options = quiz.options.join(', ');
        title = quiz.title
        flag = ``
        quizMessage = await message.channel.send(
            `**${title}**\n${options}`
        );
        if (typeof quiz.flagSrc !== 'undefined') {
            let flagSrc = quiz.flagSrc.toString();
            let country_code = flagSrc.split("/")[3].slice(0, 2);
            flag = `https://flagsapi.com/${country_code.toUpperCase()}/flat/64.png`
        }
        if (quiz.type === 'whichCountryForGivenFlag') {
            quizMessage2 = await message.channel.send(
                `${flag}`
            );
        }
    });

    // listening for the end event
    collector.on('end', (collected, reason) => {
        // reason is the one you passed above with the stop() method
        message.reply(`Thank you for playing! Always feel free to play again under !quiz`);
    });

})
    ;

client.login(token);