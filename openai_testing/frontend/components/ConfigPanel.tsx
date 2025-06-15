// src/components/ConfigPanel.tsx
"use client";

import React, { useState } from "react";
import {
  Code,
  ExternalLink,
  Home,
  Lock,
  Mail,
  Send,
  User,
  Variable,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import { emitTestCaseInitiated } from "@/components/SocketIOManager";
import AppHeader from "@/components/AppHeader";
import {
  PASSWORD,
  TEST_APP_URL,
  TEST_CASE,
  USER_INFO,
  USERNAME,
} from "@/lib/constants";

interface ConfigPanelProps {
  onSubmitted?: (testCase: string) => void;
}

export default function ConfigPanel({ onSubmitted }: ConfigPanelProps) {
  const [testCase, setTestCase] = useState(TEST_CASE);
  const [url, setUrl] = useState(TEST_APP_URL);
  const [username, setUsername] = useState(USERNAME);
  const [password, setPassword] = useState(PASSWORD);
  const [name, setName] = useState(USER_INFO.name);
  const [email, setEmail] = useState(USER_INFO.email);
  const [address, setAddress] = useState(USER_INFO.address);
  const [requiresLogin, setRequiresLogin] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formSubmitted, setFormSubmitted] = useState(false);
  const [tabValue, setTabValue] = useState<"test-case" | "variables">(
    "test-case"
  );

  // Submit handler
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    setSubmitting(true);
    setFormSubmitted(true);

    emitTestCaseInitiated({
      testCase,
      url,
      userName: username,
      password,
      loginRequired: requiresLogin,
      userInfo: JSON.stringify({
        name,
        email,
        address,
      }),
    });

    onSubmitted?.(testCase);
  };

  /* Summary view (post-submit) */
  if (formSubmitted) {
    return (
      <div className="w-full flex flex-col gap-8 justify-center items-start p-4 md:p-6 max-w-4xl mx-auto">
        {/* keep the header visible */}
        <AppHeader />

        <Card className="w-full">
          <CardHeader>
            <CardTitle>Test Case</CardTitle>
            <CardDescription>
              Your instructions have been submitted. You can track progress
              below.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm">{testCase}</pre>
          </CardContent>
        </Card>
      </div>
    );
  }

  /* Form view (pre-submit) */
  return (
    <div className="w-full flex justify-center items-start p-4 md:p-6 max-w-4xl mx-auto">
      <div className="w-full">
        <AppHeader />

        {/* Tabs */}
        <Tabs
          value={tabValue}
          onValueChange={(value) =>
            setTabValue(value as "test-case" | "variables")
          }
          className="w-full"
        >
          <TabsList className="grid grid-cols-2 w-full mb-6">
            <TabsTrigger
              value="test-case"
              className="flex items-center gap-2 py-1"
            >
              <Code className="h-4 w-4" />
              Test Case
            </TabsTrigger>
            <TabsTrigger value="variables" className="flex items-center gap-2">
              <Variable className="h-4 w-4" />
              Variables
            </TabsTrigger>
          </TabsList>

          {/* Test-case tab */}
          <TabsContent value="test-case">
            <Card>
              <CardHeader>
                <CardTitle>Test case definition</CardTitle>
                <CardDescription>
                  Describe what the frontend testing agent should do to test
                  your application in natural language.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Label htmlFor="test-case">Test instructions</Label>
                <Textarea
                  id="test-case"
                  className="min-h-[200px] resize-y mt-2"
                  value={testCase}
                  onChange={(e) => setTestCase(e.target.value)}
                  disabled={submitting}
                />
              </CardContent>
              <CardFooter className="flex justify-between">
                <Button
                  variant="outline"
                  onClick={() => setTestCase("")}
                  disabled={submitting}
                >
                  Clear
                </Button>
                <Button
                  type="button"
                  onClick={() => setTabValue("variables")}
                  disabled={submitting}
                >
                  Next: Configure Variables
                </Button>
              </CardFooter>
            </Card>
          </TabsContent>

          {/* Variables tab */}
          <TabsContent value="variables">
            <form onSubmit={handleSubmit}>
              <Card>
                <CardHeader>
                  <CardTitle>Configure Test Variables</CardTitle>
                  <CardDescription>
                    Provide the environment details and credentials (if
                    required).
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-6 max-h-[42vh] overflow-y-auto">
                  {/* URL */}
                  <div className="flex items-center gap-3">
                    <Label
                      htmlFor="url"
                      className="flex items-center gap-2 whitespace-nowrap w-24"
                    >
                      <ExternalLink className="h-4 w-4 text-muted-foreground" />
                      URL
                    </Label>
                    <Input
                      id="url"
                      type="url"
                      placeholder="http://localhost:3001"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      disabled={submitting}
                      className="flex-1"
                    />
                  </div>

                  <Separator />

                  {/* Credentials */}
                  <div className="space-y-4">
                    <div className="flex gap-6 items-center">
                      {/* Login toggle */}
                      <div className="flex items-center gap-3">
                        <Switch
                          id="requires-login"
                          checked={requiresLogin}
                          onCheckedChange={setRequiresLogin}
                          disabled={submitting}
                        />
                        <Label htmlFor="requires-login">Login</Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label
                          htmlFor="username"
                          className="flex items-center gap-2 whitespace-nowrap w-24"
                        >
                          <User className="h-4 w-4 text-muted-foreground" />
                          Username
                        </Label>
                        <Input
                          id="username"
                          type="text"
                          autoComplete="username"
                          placeholder="admin"
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          disabled={submitting || !requiresLogin}
                          className="flex-1"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <Label
                          htmlFor="password"
                          className="flex items-center gap-2 whitespace-nowrap w-24"
                        >
                          <Lock className="h-4 w-4 text-muted-foreground" />
                          Password
                        </Label>
                        <Input
                          id="password"
                          type="password"
                          placeholder="••••••••••"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          disabled={submitting || !requiresLogin}
                          className="flex-1"
                        />
                      </div>
                    </div>

                    <Separator />

                    {/* User info */}

                    <div className="space-y-3">
                      <Label htmlFor="requires-login">User info</Label>

                      <div className="flex gap-6 items-center">
                        <div className="flex items-center gap-2">
                          <Label
                            htmlFor="name"
                            className="flex items-center gap-2 whitespace-nowrap w-24"
                          >
                            <User className="h-4 w-4 text-muted-foreground" />
                            Name
                          </Label>
                          <Input
                            id="name"
                            type="text"
                            autoComplete="name"
                            placeholder="John Doe"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="flex-1"
                          />
                        </div>
                        <div className="flex flex-1 items-center gap-2">
                          <Label
                            htmlFor="email"
                            className="flex items-center gap-2 whitespace-nowrap w-24"
                          >
                            <Mail className="h-4 w-4 text-muted-foreground" />
                            Email
                          </Label>
                          <Input
                            id="email"
                            type="email"
                            autoComplete="email"
                            placeholder="john.doe@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="flex-1"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label
                          htmlFor="address"
                          className="flex items-center gap-2 whitespace-nowrap w-24"
                        >
                          <Home className="h-4 w-4 text-muted-foreground" />
                          Address
                        </Label>
                        <Input
                          id="address"
                          type="text"
                          autoComplete="address"
                          placeholder="123 Main St, Anytown, USA"
                          value={address}
                          onChange={(e) => setAddress(e.target.value)}
                          disabled={submitting || !requiresLogin}
                          className="flex-1"
                        />
                      </div>
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="flex justify-between">
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setTabValue("test-case")}
                    disabled={submitting}
                  >
                    Back
                  </Button>

                  <Button type="submit" className="gap-2" disabled={submitting}>
                    <Send className="h-4 w-4" />
                    {submitting ? "Submitting…" : "Submit"}
                  </Button>
                </CardFooter>
              </Card>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
