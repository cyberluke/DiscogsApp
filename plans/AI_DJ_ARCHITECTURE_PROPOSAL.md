# AI DJ

# Discogs Music Intelligence

# Architecture Proposal

The Discogs application should evolve from a Discogs browser into an AI-powered Music Companion.

This is not a chatbot.

This is not a recommendation engine.

This is an AI DJ that understands:

- The user's own collection
- What is currently playing
- Conversational requests
- Music history
- Musical style
- Transitions between tracks

The Discogs application becomes the authoritative Music Intelligence Service.

Soul Platform will later consume its REST API.

## Architecture

```text
                Angular UI
                     |
                     v
               AI Chat Window
                     |
                     v
             Conversation Service
                     |
                     v
              Music Intelligence
                     |
       +-------------+-------------+
       |             |             |
       v             v             v
 Current Track   Collection    Azure OpenAI
       |             |             |
       +-------------+-------------+
                     |
                     v
            Recommendation Engine
                     |
                     v
               Playback Commands
```

## AI Personality

The assistant is not a generic chatbot.

It is an experienced music collector and DJ specializing in European electronic music between approximately 1988 and 2010.

It should sound like someone who has spent decades collecting CDs, knows labels, producers, and scenes, but never behaves like a Wikipedia article.

It should be conversational.

## Current Context

Every AI request should automatically include:

- Current release
- Current track
- Artist
- Year
- Country
- Genres
- Styles
- Track duration
- Discogs metadata
- Current deck
- Current CD
- Current playback position
- Current playlist
- Recently played tracks
- Collection statistics

No internet lookup should be required.

## Conversation Examples

```text
User: "I want some Eurodance."

AI:
Current song
-> Collection
-> Recommendation
```

Additional examples:

- "Something harder."
- "Less cheesy."
- "Play something similar."
- "I want female vocals."
- "Surprise me."
- "Something perfect for night driving."
- "Back to trance."
- "Play a forgotten classic."
- "Something from Germany."
- "Play one guilty pleasure."

## Recommendation Philosophy

Recommendations should not rely only on:

- Genre
- Style
- Label

Instead they should consider musical DNA.

Examples:

```text
Current:
Captain Hollywood

Recommended:
Intermission
Magic Affair
Kim Sanders
Pharao
```

```text
Current:
Scooter

Recommended:
Hypetraxx
Mega Lo Mania
Triple Concept
```

```text
Current:
Whitney Houston

Recommended:
Alexia
Bellini
2 Brothers On The 4th Floor
```

The recommendation should explain why.

## Relative Navigation

The AI should understand movement.

Examples:

```text
User: "More trance"

Current:
Captain Hollywood

Recommendation path:
DJ Sakin
Paul van Dyk
```

```text
User: "Less commercial"

Result:
Underground recommendation
```

```text
User: "More melodic"

Result:
Different recommendation
```

```text
User: "Faster"

Result:
Higher BPM recommendation
```

```text
User: "More emotional"

Result:
Different scene
```

## Explain Recommendation

Every recommendation should include:

1. Why this recommendation fits.
2. Which musical characteristics are shared.
3. Which characteristics differ.

Never simply output:

```text
Artist
Track
Done
```

## Collection Awareness

The AI should know this collection.

Not Spotify.

Not the internet.

Questions like "What hidden gems do I own?" should be answered using the user's own collection.

## Collection Intelligence

Examples:

- Most represented labels
- Most represented countries
- Most common years
- Most energetic releases
- Most nostalgic releases
- Most underrated releases
- Most surprising release
- Hidden gems
- Forgotten classics
- Collection outliers
- One-hit wonders

## AI Metadata

Every release should receive cached AI analysis.

Example:

```json
{
  "ai": {
    "scene": "",
    "summary": "",
    "energy": 0,
    "danceability": 0,
    "cheese": 0,
    "nostalgia": 0,
    "commercial": 0,
    "club": 0,
    "festival": 0,
    "radio": 0,
    "guiltyPleasure": false,
    "keywords": [],
    "mood": [],
    "recommendedAfter": [],
    "similarArtists": [],
    "historicalImportance": "",
    "productionStyle": ""
  }
}
```

Cached permanently.

## Chat Window

New page: AI DJ.

Layout:

```text
----------------------------------------------------
Current Playing

Cover
Track
Artist
Playback

-------------------------------------
Conversation
-------------------------------------
Suggestions
-------------------------------------
Input

Ask about your music...
----------------------------------------------------
```

## Quick Suggestions

Buttons:

- Play something similar
- More energetic
- More melodic
- More trance
- More house
- More Eurodance
- More underground
- Night driving
- Workout
- Surprise me
- Hidden gem
- Forgotten classic
- Continue this vibe

## Actions

Every AI answer may contain:

- Play
- Queue Next
- Replace Queue
- Open Release
- Explain

## Recommendation Output

Instead of:

```text
Artist
-> Track
-> Done
```

Return:

- Track
- Reason
- Confidence
- Musical DNA
- Optional explanation

## REST API

Prepare for Soul Platform.

### GET /api/chat/context

Returns:

- Now Playing
- Collection
- Recent history

### POST /api/chat

Request:

- Conversation

Returns:

- AI response
- Suggested tracks
- Actions

### POST /api/play

Request:

- Track recommendation

Result:

- Starts playback

### GET /api/recommendations/current

Returns recommendations for the currently playing track.

### GET /api/releases/{id}/ai

Returns cached AI metadata.

## Conversation Memory

Conversation should remember:

- Current topic
- Current vibe
- Current listening session

Example:

```text
User: "I want some Eurodance."

Later:
"Something less cheesy."

The AI should understand: less cheesy than the current recommendations.
```

## Implementation

Create:

```text
services/
  ai/
    AzureOpenAIClient
    PromptBuilder
    ConversationContextBuilder
    MusicRecommendationService
    MusicAnalysisService
    MusicCache
    RecommendationParser
    ChatService
    PlaylistActionService
```

## Prompt Design

The prompt should include:

- Current playback
- Collection metadata
- Conversation history
- User request

Return JSON only.

## Rules

- Never hallucinate tracks.
- Recommend only tracks present in the local collection.
- If no suitable recommendation exists, say so.
- Never recommend Spotify.
- Never recommend YouTube.
- Never recommend external services.
- The user's own collection is the universe.

## Future Integration

This AI DJ will later become a Persona inside the Soul Platform.

Discogs App remains responsible for:

- Music knowledge
- Music metadata
- Recommendations
- Collection analysis

Soul Platform consumes these capabilities through REST.

The AI DJ should therefore be implemented as an independent service with no dependency on Angular UI.