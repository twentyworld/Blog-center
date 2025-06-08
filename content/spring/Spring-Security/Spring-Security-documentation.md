## Spring Security
---

Spring Security is a framework that focuses on providing both authentication and authorization to Java applications. Like all Spring projects, the real power of Spring Security is found in how easily it can be extended to meet custom requirements


>  spring security实现方式大致可以分为这几种：
>  1. 配置文件实现，只需要在配置文件中指定拦截的url所需要权限、配置userDetailsService指定用户名、密码、对应权限，就可以实现。
>  2. 实现UserDetailsService，loadUserByUsername(String userName)方法，根据userName来实现自己的业务逻辑返回UserDetails的实现类，需要自定义User类实现UserDetails，比较重要的方法是getAuthorities()，用来返回该用户所拥有的权限。
>  3. 通过自定义filter重写spring security拦截器，实现动态过滤用户权限。
>  4. 通过自定义filter重写spring security拦截器，实现自定义参数来检验用户，并且过滤权限。


---
#### Java Configuration

The first step is to create our Spring Security Java Configuration。
```java
@EnableWebSecurity
public class WebSecurityConfig implements WebMvcConfigurer {

	@Bean
	public UserDetailsService userDetailsService() throws Exception {
		InMemoryUserDetailsManager manager = new InMemoryUserDetailsManager();
		manager.createUser(User.withDefaultPasswordEncoder().username("user").password("password").roles("USER").build());
		return manager;
	}
}
```

The next step is to register the springSecurityFilterChain with the war.
Spring Security provides a base class AbstractSecurityWebApplicationInitializer that will ensure the springSecurityFilterChain gets registered for you. The way in which we use AbstractSecurityWebApplicationInitializer differs depending on if we are already using Spring or if Spring Security is the only Spring component in our application.

- If you are not using Spring or Spring MVC, you will need to pass in the WebSecurityConfig into the superclass to ensure the configuration is picked up. You can find an example below:
  ```java
  public class SecurityWebApplicationInitializer
  	extends AbstractSecurityWebApplicationInitializer {
  	public SecurityWebApplicationInitializer() {
  		super(WebSecurityConfig.class);
  	}
  }
  ```
- If we were using Spring elsewhere in our application we probably already had a WebApplicationInitializer that is loading our Spring Configuration. If we use the previous configuration we would get an error. Instead, we should register Spring Security with the existing ApplicationContext
  ```java
  public class MvcWebApplicationInitializer extends
  		AbstractAnnotationConfigDispatcherServletInitializer {
  	@Override
  	protected Class<?>[] getRootConfigClasses() {
  		return new Class[] { WebSecurityConfig.class };
  	}

  	// ... other overrides ...
  }
  ```
---
#### HttpSecurity
the WebSecurityConfigurerAdapter provides a default configuration in the configure(HttpSecurity http) method that looks like:
```java
protected void configure(HttpSecurity http) throws Exception {
	http
		.authorizeRequests()
			.anyRequest().authenticated()
			.and()
		.formLogin()
			.and()
		.httpBasic();
}
```
The default configuration above:
- Ensures that any request to our application requires the user to be authenticated
- Allows users to authenticate with form based login
- Allows users to authenticate with HTTP Basic authentication

---
#### Java Configuration and Form Login
While the automatically generated log in page is convenient to get up and running quickly, most applications will want to provide their own log in page. To do so we can update our configuration as seen below:
```java
protected void configure(HttpSecurity http) throws Exception {
	http
		.authorizeRequests()
			.anyRequest().authenticated()
			.and()
		.formLogin()
			.loginPage("/login")                                                             1
			.permitAll();                                                                    2
}
```
1. The updated configuration specifies the location of the log in page.
2. We must grant all users (i.e. unauthenticated users) access to our log in page. The formLogin().permitAll() method allows granting access to all users for all URLs associated with form based log in.

---
#### Authorize Requests

We can specify custom requirements for our URLs by adding multiple children to our http.authorizeRequests() method. For example:
```java
protected void configure(HttpSecurity http) throws Exception {
	http
		.authorizeRequests()                                                              1
			.antMatchers("/resources/**", "/signup", "/about").permitAll()                  2
			.antMatchers("/admin/**").hasRole("ADMIN")                                      3
			.antMatchers("/db/**").access("hasRole('ADMIN') and hasRole('DBA')")            4
			.anyRequest().authenticated()                                                   5
			.and()
		// ...
		.formLogin();
}
```
1.  There are multiple children to the http.authorizeRequests() method each matcher is considered in the order they were declared.
2.  We specified multiple URL patterns that any user can access. Specifically, any user can access a request if the URL starts with "/resources/", equals "/signup", or equals "/about".
3.  Any URL that starts with "/admin/" will be restricted to users who have the role "ROLE_ADMIN". You will notice that since we are invoking the hasRole method we do not need to specify the "ROLE_" prefix.
4.  Any URL that starts with "/db/" requires the user to have both "ROLE_ADMIN" and "ROLE_DBA". You will notice that since we are using the hasRole expression we do not need to specify the "ROLE_" prefix.
5.  Any URL that has not already been matched on only requires that the user be authenticated

---
#### Handling Logouts

When using the WebSecurityConfigurerAdapter, logout capabilities are automatically applied. The default is that accessing the URL /logout will log the user out by:

- Invalidating the HTTP Session
- Cleaning up any RememberMe authentication that was configured
- Clearing the SecurityContextHolder
- Redirect to /login?logout
- Similar to configuring login capabilities, however, you also have various options to further customize your logout requirements:

```java
protected void configure(HttpSecurity http) throws Exception {
	http
		.logout()                                                                   1
			.logoutUrl("/my/logout")                                                  2
			.logoutSuccessUrl("/my/index")                                            3
			.logoutSuccessHandler(logoutSuccessHandler)                               4
			.invalidateHttpSession(true)                                              5
			.addLogoutHandler(logoutHandler)                                          6
			.deleteCookies(cookieNamesToClear)                                        7
			.and()
		...
}
```
1.  Provides logout support. This is automatically applied when using WebSecurityConfigurerAdapter.
2.  The URL that triggers log out to occur (default is /logout). If CSRF protection is enabled (default), then the request must also be a POST. For more information, please consult the JavaDoc.
3.  The URL to redirect to after logout has occurred. The default is /login?logout. For more information, please consult the JavaDoc.
4.  Let’s you specify a custom LogoutSuccessHandler. If this is specified, logoutSuccessUrl() is ignored. For more information, please consult the JavaDoc.
5.  Specify whether to invalidate the HttpSession at the time of logout. This is true by default. Configures the SecurityContextLogoutHandler under the covers. For more information, please consult the JavaDoc.
6.  Adds a LogoutHandler. SecurityContextLogoutHandler is added as the last LogoutHandler by default.
7.  Allows specifying the names of cookies to be removed on logout success. This is a shortcut for adding a CookieClearingLogoutHandler explicitly.

Generally, in order to customize logout functionality, you can add LogoutHandler and/or LogoutSuccessHandler implementations. For many common scenarios, these handlers are applied under the covers when using the fluent API.

##### LogoutHandler
LogoutHandler implementations indicate classes that are able to participate in logout handling. They are expected to be invoked to perform necessary clean-up. As such they should not throw exceptions. Various implementations are provided:

- PersistentTokenBasedRememberMeServices
- TokenBasedRememberMeServices
- CookieClearingLogoutHandler
- CsrfLogoutHandler
- SecurityContextLogoutHandler


##### LogoutSuccessHandler
The LogoutSuccessHandler is called after a successful logout by the LogoutFilter, to handle e.g. redirection or forwarding to the appropriate destination. Note that the interface is almost the same as the LogoutHandler but may raise an exception.

---
#### WebFlux Security

<font color="RED">**will add later.**</font>

---
#### OAuth 2.0 Login

Spring Boot 2.0 brings full auto-configuration capabilities for OAuth 2.0 Login.

Below shows how to configure the OAuth 2.0 Login sample using Google as the Authentication Provider and covers the following topics:

- Initial setup
- Setting the redirect URI
- Configure application.yml
- Boot up the application

<font color="RED">**will add some demo code later.**</font>

---
#### Authentication
more advanced options for configuring authentication.

##### In-Memory Authentication
We have already seen an example of configuring in-memory authentication for a single user. Below is an example to configure multiple users:
```java
@Bean
public UserDetailsService userDetailsService() throws Exception {
	// ensure the passwords are encoded properly
	UserBuilder users = User.withDefaultPasswordEncoder();
	InMemoryUserDetailsManager manager = new InMemoryUserDetailsManager();
	manager.createUser(users.username("user").password("password").roles("USER").build());
	manager.createUser(users.username("admin").password("password").roles("USER","ADMIN").build());
	return manager;
}
```

##### JDBC Authentication
You can find the updates to support JDBC based authentication. The example below assumes that you have already defined a DataSource within your application. The jdbc-javaconfig sample provides a complete example of using JDBC based authentication.
```java
@Autowired
private DataSource dataSource;

@Autowired
public void configureGlobal(AuthenticationManagerBuilder auth) throws Exception {
	// ensure the passwords are encoded properly
	UserBuilder users = User.withDefaultPasswordEncoder();
	auth
		.jdbcAuthentication()
			.dataSource(dataSource)
			.withDefaultSchema()
			.withUser(users.username("user").password("password").roles("USER"))
			.withUser(users.username("admin").password("password").roles("USER","ADMIN"));
}
```

##### LDAP Authentication
You can find the updates to support LDAP based authentication. The ldap-javaconfig sample provides a complete example of using LDAP based authentication.


##### AuthenticationProvider.
You can define custom authentication by exposing a custom AuthenticationProvider as a bean. For example, the following will customize authentication assuming that SpringAuthenticationProvider implements AuthenticationProvider:
```java
@Bean
public SpringAuthenticationProvider springAuthenticationProvider() {
	return new SpringAuthenticationProvider();
}
```

##### UserDetailsService
You can define custom authentication by exposing a custom UserDetailsService as a bean. For example, the following will customize authentication assuming that SpringDataUserDetailsService implements UserDetailsService:
>This is only used if the AuthenticationManagerBuilder has not been populated and no AuthenticationProviderBean is defined.
```java
@Bean
public SpringDataUserDetailsService springDataUserDetailsService() {
	return new SpringDataUserDetailsService();
}
```
You can also customize how passwords are encoded by exposing a PasswordEncoder as a bean. For example, if you use bcrypt you can add a bean definition as shown below:
```java
@Bean
public BCryptPasswordEncoder passwordEncoder() {
	return new BCryptPasswordEncoder();
}
```
---
#### Multiple HttpSecurity
We can configure multiple HttpSecurity instances just as we can have multiple <http> blocks. The key is to extend the WebSecurityConfigurationAdapter multiple times. For example, the following is an example of having a different configuration for URL’s that start with /api/.
```java
@EnableWebSecurity
public class MultiHttpSecurityConfig {
	@Bean                                                                    1
	public UserDetailsService userDetailsService() throws Exception {
		// ensure the passwords are encoded properly
		UserBuilder users = User.withDefaultPasswordEncoder();
		InMemoryUserDetailsManager manager = new InMemoryUserDetailsManager();
		manager.createUser(users.username("user").password("password").roles("USER").build());
		manager.createUser(users.username("admin").password("password").roles("USER","ADMIN").build());
		return manager;
	}

	@Configuration
	@Order(1)                                                                2
	public static class ApiWebSecurityConfigurationAdapter extends WebSecurityConfigurerAdapter {
		protected void configure(HttpSecurity http) throws Exception {
			http
				.antMatcher("/api/**")                                            3
				.authorizeRequests()
					.anyRequest().hasRole("ADMIN")
					.and()
				.httpBasic();
		}
	}

	@Configuration                                                          4
	public static class FormLoginWebSecurityConfigurerAdapter extends WebSecurityConfigurerAdapter {

		@Override
		protected void configure(HttpSecurity http) throws Exception {
			http
				.authorizeRequests()
					.anyRequest().authenticated()
					.and()
				.formLogin();
		}
	}
}
```

1. Configure Authentication as normal
2. Create an instance of WebSecurityConfigurerAdapter that contains @Order to specify which WebSecurityConfigurerAdapter should be considered first.
3. The http.antMatcher states that this HttpSecurity will only be applicable to URLs that start with /api/
4. Create another instance of WebSecurityConfigurerAdapter. If the URL does not start with /api/ this configuration will be used. This configuration is considered after ApiWebSecurityConfigurationAdapter since it has an @Order value after 1 (no @Order defaults to last).

---
#### Method Security

> 在Spring security的使用中，为了对方法进行权限控制，通常采用的三个注解，就是@Secured(), @PreAuthorize() 及 @RolesAllowed()。
>
> 现在举例，比如修改用户密码，必须是ADMIN的权限才可以。则可以用下面三种方法：
> ```
> @Secured({"ROLE_ADMIN"})
> public void changePassword(String username, String password);
>
> @RolesAllowed({"ROLE_ADMIN"})
> public void changePassword(String username, String password);
>
> @PreAuthorize("hasRole(‘ROLE_ADMIN‘)")
> public void changePassword(String username, String password);
> ```

From version 2.0 onwards Spring Security has improved support substantially for adding security to your service layer methods.

You can apply security to a single bean, using the intercept-methods element to decorate the bean declaration, or you can secure multiple beans across the entire service layer using the AspectJ style pointcuts.


##### EnableGlobalMethodSecurity
We can enable annotation-based security using the @EnableGlobalMethodSecurity annotation on any @Configuration instance. For example, the following would enable Spring Security’s @Secured annotation.
```java
@EnableGlobalMethodSecurity(securedEnabled = true)
public class MethodSecurityConfig {
// ...
}
```
Adding an annotation to a method (on a class or interface) would then limit the access to that method accordingly. Spring Security’s native annotation support defines a set of attributes for the method. These will be passed to the AccessDecisionManager for it to make the actual decision:
```java
public interface BankService {

	@Secured("IS_AUTHENTICATED_ANONYMOUSLY")
	public Account readAccount(Long id);

	@Secured("IS_AUTHENTICATED_ANONYMOUSLY")
	public Account[] findAccounts();

	@Secured("ROLE_TELLER")
	public Account post(Account account, double amount);
}
```

##### GlobalMethodSecurityConfiguration
Sometimes you may need to perform operations that are more complicated than are possible with the @EnableGlobalMethodSecurity annotation allow. For these instances, you can extend the GlobalMethodSecurityConfiguration ensuring that the @EnableGlobalMethodSecurity annotation is present on your subclass.

For example, if wanted to provide a custom MethodSecurityExpressionHandler,  could use the following configuration:
```java
@EnableGlobalMethodSecurity(prePostEnabled = true)
public class MethodSecurityConfig extends GlobalMethodSecurityConfiguration {
	@Override
	protected MethodSecurityExpressionHandler createExpressionHandler() {
		// ... create and return custom MethodSecurityExpressionHandler ...
		return expressionHandler;
	}
}
```


##### EnableReactiveMethodSecurity

---
#### Post Processing Configured Objects
Spring Security’s Java Configuration does not expose every property of every object that it configures. This simplifies the configuration for a majority of users. Afterall, if every property was exposed, users could use standard bean configuration.
```java
@Override
protected void configure(HttpSecurity http) throws Exception {
	http
		.authorizeRequests()
			.anyRequest().authenticated()
			.withObjectPostProcessor(new ObjectPostProcessor<FilterSecurityInterceptor>() {
				public <O extends FilterSecurityInterceptor> O postProcess(
						O fsi) {
					fsi.setPublishAuthorizationSuccess(true);
					return fsi;
				}
			});
}
```

---
#### Custom DSLs
You can provide your own custom DSLs in Spring Security. For example, you might have something that looks like this:
```java
public class MyCustomDsl extends AbstractHttpConfigurer<MyCustomDsl, HttpSecurity> {
	private boolean flag;

	@Override
	public void init(H http) throws Exception {
		// any method that adds another configurer
		// must be done in the init method
		http.csrf().disable();
	}

	@Override
	public void configure(H http) throws Exception {
		ApplicationContext context = http.getSharedObject(ApplicationContext.class);

		// here we lookup from the ApplicationContext. You can also just create a new instance.
		MyFilter myFilter = context.getBean(MyFilter.class);
		myFilter.setFlag(flag);
		http.addFilterBefore(myFilter, UsernamePasswordAuthenticationFilter.class);
	}

	public MyCustomDsl flag(boolean value) {
		this.flag = value;
		return this;
	}

	public static MyCustomDsl customDsl() {
		return new MyCustomDsl();
	}
}


@EnableWebSecurity
public class Config extends WebSecurityConfigurerAdapter {
	@Override
	protected void configure(HttpSecurity http) throws Exception {
		http
			.apply(customDsl())
				.flag(true)
				.and()
			...;
	}
}
```


## 2. Architecture and Implementation
---
### Core Components

#### SecurityContextHolder, SecurityContext and Authentication Objects

The most fundamental object is SecurityContextHolder. This is where we store details of the present security context of the application, which includes details of the principal currently using the application. By default the SecurityContextHolder uses a ThreadLocal to store these details, which means that the security context is always available to methods in the same thread of execution, even if the security context is not explicitly passed around as an argument to those methods. Using a ThreadLocal in this way is quite safe if care is taken to clear the thread after the present principal’s request is processed. Of course, Spring Security takes care of this for you automatically so there is no need to worry about it.

Some applications aren’t entirely suitable for using a ThreadLocal, because of the specific way they work with threads. For example, a Swing client might want all threads in a Java Virtual Machine to use the same security context. SecurityContextHolder can be configured with a strategy on startup to specify how you would like the context to be stored. For a standalone application you would use the SecurityContextHolder.MODE_GLOBAL strategy. Other applications might want to have threads spawned by the secure thread also assume the same security identity. This is achieved by using SecurityContextHolder.MODE_INHERITABLETHREADLOCAL. You can change the mode from the default SecurityContextHolder.MODE_THREADLOCAL in two ways. The first is to set a system property, the second is to call a static method on SecurityContextHolder. Most applications won’t need to change from the default, but if you do, take a look at the JavaDoc for SecurityContextHolder to learn more.


###### Obtaining information about the current user：

Inside the SecurityContextHolder we store details of the principal currently interacting with the application. Spring Security uses an Authentication object to represent this information.

 You won’t normally need to create an Authentication object yourself, but it is fairly common for users to query the Authentication object.

 You can use the following code block - from anywhere in your application - to obtain the name of the currently authenticated user, for example:
 ```java
 Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();

 if (principal instanceof UserDetails) {
    String username = ((UserDetails)principal).getUsername();
 } else {
    String username = principal.toString();
 }
 ```
> The object returned by the call to getContext() is an instance of the SecurityContext interface.

> most authentication mechanisms within Spring Security return an instance of UserDetails as the principal.

---

#### The UserDetailsService


Another item to note from the above code fragment is that you can obtain a principal from the Authentication object.

The principal is just an Object. Most of the time this can be cast into a UserDetails object. UserDetails is a core interface in Spring Security.


a special interface called UserDetailsService. The only method on this interface accepts a String-based username argument and returns a UserDetails:
```java
UserDetails loadUserByUsername(String username) throws UsernameNotFoundException;
```
> loadUserByUsername() used throughout the framework whenever information on a user is required.

There is often some confusion about UserDetailsService. It is purely a DAO for user data and performs no other function other than to supply that data to other components within the framework. In particular, it does not authenticate the user, which is done by the AuthenticationManager. In many cases it makes more sense to implement AuthenticationProvider directly if you require a custom authentication process.

#### GrantedAuthority

Besides the principal, another important method provided by Authentication is getAuthorities(). This method provides an array of GrantedAuthority objects.

A GrantedAuthority is, not surprisingly, an authority that is granted to the principal. Such authorities are usually "roles", such as ROLE_ADMINISTRATOR or ROLE_HR_SUPERVISOR. These roles are later on configured for web authorization, method authorization and domain object authorization.

GrantedAuthority objects are usually loaded by the UserDetailsService.

Just to recap, the major building blocks of Spring Security that we’ve seen so far are:

- SecurityContextHolder, to provide access to the SecurityContext.
- SecurityContext, to hold the Authentication and possibly request-specific security information.
- Authentication, to represent the principal in a Spring Security-specific manner.
- GrantedAuthority, to reflect the application-wide permissions granted to a principal.
- UserDetails, to provide the necessary information to build an Authentication object from your application’s DAOs or other source of security data.
- UserDetailsService, to create a UserDetails when passed in a String-based username (or certificate ID or the like).

---

### Authentication身份验证
**a standard authentication scenario:**
>
>  1. A user is prompted to log in with a username and password.
>  2. The system (successfully) verifies that the password is correct for the username.
>  3. The context information for that user is obtained (their list of roles and so on).
>  4. A security context is established for the user
>  5. The user proceeds, potentially to perform some operation which is potentially protected by an access control mechanism which checks the required permissions for the operation against the current security context information.

The first three items constitute the authentication process so we’ll take a look at how these take place within Spring Security.
1. The username and password are obtained and combined into an instance of UsernamePasswordAuthenticationToken (an instance of the Authentication interface, which we saw earlier).
2. The token is passed to an instance of AuthenticationManager for validation.
3. The AuthenticationManager returns a fully populated Authentication instance on successful authentication.
4. The security context is established by calling SecurityContextHolder.getContext().setAuthentication(…​), passing in the returned authentication object.

example code:
```java
public class test {
    private static AuthenticationManager am = new SampleAuthenticationManager();

    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));

        while (true) {
            System.out.println("Please enter your username:");
            String name = in.readLine();
            System.out.println("Please enter your password:");
            String password = in.readLine();
            try {
                Authentication request = new UsernamePasswordAuthenticationToken(name, password);
                Authentication result = am.authenticate(request);
                SecurityContextHolder.getContext().setAuthentication(result);
                break;
            } catch (AuthenticationException e) {
                System.out.println("Authentication failed: " + e.getMessage());
            }
        }
        System.out.println("Successfully authenticated. Security context contains: " + SecurityContextHolder.getContext().getAuthentication());
    }
}

class SampleAuthenticationManager implements AuthenticationManager {
    static final List<GrantedAuthority> AUTHORITIES = new ArrayList<>();

    static {
        AUTHORITIES.add(new SimpleGrantedAuthority("ROLE_USER"));
    }

    public Authentication authenticate(Authentication auth) throws AuthenticationException {
        if (auth.getName().equals(auth.getCredentials())) {
            return new UsernamePasswordAuthenticationToken(auth.getName(), auth.getCredentials(), AUTHORITIES);
        }
        throw new BadCredentialsException("Bad Credentials");
    }
}
```
A user is authenticated when the SecurityContextHolder contains a fully populated Authentication object.

In fact, Spring Security doesn’t mind how you put the Authentication object inside the SecurityContextHolder. The only critical requirement is that the SecurityContextHolder contains an Authentication which represents a principal before the AbstractSecurityInterceptor (which we’ll see more about later) needs to authorize a user operation.


### Authentication in a Web Application
> Consider a typical web application’s authentication process:
>
> - You visit the home page, and click on a link.
> - A request goes to the server, and the server decides that you’ve asked for a protected resource.
> - As you’re not presently authenticated, the server sends back a response indicating that you must authenticate. The response will either be an HTTP response code, or a redirect to a particular web page.
> - Depending on the authentication mechanism, your browser will either redirect to the specific web page so that you can fill out the form, or the browser will somehow retrieve your identity (via a BASIC authentication dialogue box, a cookie, a X.509 certificate etc.).
> - The browser will send back a response to the server. This will either be an HTTP POST containing the contents of the form that you filled out, or an HTTP header containing your authentication details.
> - Next the server will decide whether or not the presented credentials are valid. If they’re valid, the next step will happen. If they’re invalid, usually your browser will be asked to try again (so you return to step two above).
> - The original request that you made to cause the authentication process will be retried. Hopefully you’ve authenticated with sufficient granted authorities to access the protected resource. If you have sufficient access, the request will be successful. Otherwise, you’ll receive back an HTTP error code 403, which means "forbidden".

Spring Security has distinct classes responsible for most of the steps described above. The main participants (in the order that they are used) are the ExceptionTranslationFilter, an AuthenticationEntryPoint and an "authentication mechanism", which is responsible for calling the AuthenticationManager which we saw in the previous section.

###### ExceptionTranslationFilter
ExceptionTranslationFilter is a Spring Security filter that has responsibility for detecting any Spring Security exceptions that are thrown.

Such exceptions will generally be thrown by an AbstractSecurityInterceptor, which is the main provider of authorization services.

###### AuthenticationEntryPoint
The AuthenticationEntryPoint is responsible for step three in the above list.

######  Authentication Mechanism
Once your browser submits your authentication credentials (either as an HTTP form post or HTTP header) there needs to be something on the server that "collects" these authentication details. By now we’re at step six in the above list.

Once the authentication details have been collected from the user agent, an Authentication "request" object is built and then presented to the AuthenticationManager.

After the authentication mechanism receives back the fully-populated Authentication object, it will deem the request valid, put the Authentication into the SecurityContextHolder, and cause the original request to be retried (step seven above). If, on the other hand, the AuthenticationManager rejected the request, the authentication mechanism will ask the user agent to retry (step two above).

###### Storing the SecurityContext between requests
Depending on the type of application, there may need to be a strategy in place to store the security context between user operations.

In Spring Security, the responsibility for storing the SecurityContext between requests falls to the SecurityContextPersistenceFilter, which by default stores the context as an HttpSession attribute between HTTP requests. It restores the context to the SecurityContextHolder for each request and, crucially, clears the SecurityContextHolder when the request completes.

---

### Access-Control (Authorization) in Spring Security
The main interface responsible for making access-control decisions in Spring Security is the AccessDecisionManager. It has a decide method which takes an Authentication object representing the principal requesting access. "secure object" (see below) and a list of security metadata attributes which apply for the object (such as a list of roles which are required for access to be granted).


##### Security and AOP Advice
Spring Security provides an around advice for method invocations as well as web requests. We achieve an around advice for method invocations using Spring’s standard AOP support and we achieve an around advice for web requests using a standard Filter.

the key point to understand is that Spring Security can help you protect method invocations as well as web requests.

##### Secure Objects and the AbstractSecurityInterceptor
The most common examples are method invocations and web requests.


Each supported secure object type has its own interceptor class, which is a subclass of AbstractSecurityInterceptor.
Importantly, by the time the AbstractSecurityInterceptor is called, the SecurityContextHolder will contain a valid Authentication if the principal has been authenticated.


>AbstractSecurityInterceptor provides a consistent workflow for handling secure object requests, typically:
>1. Look up the "configuration attributes" associated with the present request
>2. Submitting the secure object, current Authentication and configuration attributes to the AccessDecisionManager for an authorization decision
>3. Optionally change the Authentication under which the invocation takes place
>4. Allow the secure object invocation to proceed (assuming access was granted)
>5. Call the AfterInvocationManager if configured, once the invocation has returned. If the invocation raised an exception, the AfterInvocationManager will not be invoked.

for more question, please visit [this][1];

the uml is

![uml][2]


----

### Localization

Spring Security supports localization of exception messages that end users are likely to see. If your application is designed for English-speaking users, you don’t need to do anything as by default all Security messages are in English. If you need to support other locales, everything you need to know is contained in this section.



-----
#### Samples

https://docs.spring.io/spring-security/site/docs/current/guides/html5//helloworld-boot.html
https://docs.spring.io/spring-security/site/docs/current/guides/html5//form-javaconfig.html

## 3. Core Services
---

Now that we have a high-level overview of the Spring Security architecture and its core classes, let’s take a closer look at one or two of the core interfaces and their implementations, in particular the AuthenticationManager, UserDetailsService and the AccessDecisionManager. These crop up regularly throughout the remainder of this document so it’s important you know how they are configured and how they operate.


---

### AuthenticationManager, ProviderManager and AuthenticationProvider

The AuthenticationManager is just an interface, so the implementation can be anything we choose, but how does it work in practice?

The default implementation in Spring Security is called ProviderManager and rather than handling the authentication request itself, it delegates to a list of configured AuthenticationProvider s, each of which is queried in turn to see if it can perform the authentication. Each provider will either throw an exception or return a fully populated Authentication object.
The most common approach to verifying an authentication request is to load the corresponding UserDetails and check the loaded password against the one that has been entered by the user. This is the approach used by the DaoAuthenticationProvider。
The loaded UserDetails object - and particularly the GrantedAuthority s it contains - will be used when building the fully populated Authentication object which is returned from a successful authentication and stored in the SecurityContext.

```xml
<bean id="authenticationManager"
		class="org.springframework.security.authentication.ProviderManager">
	<constructor-arg>
		<list>
			<ref local="daoAuthenticationProvider"/>
			<ref local="anonymousAuthenticationProvider"/>
			<ref local="ldapAuthenticationProvider"/>
		</list>
	</constructor-arg>
</bean>
```
In the above example we have three providers. They are tried in the order shown (which is implied by the use of a List), with each provider able to attempt authentication, or skip authentication by simply returning null. If all implementations return null, the ProviderManager will throw a ProviderNotFoundException. If you’re interested in learning more about chaining providers, please refer to the ProviderManager Javadoc.

Authentication mechanisms such as a web form-login processing filter are injected with a reference to the ProviderManager and will call it to handle their authentication requests. The providers you require will sometimes be interchangeable with the authentication mechanisms, while at other times they will depend on a specific authentication mechanism. For example, DaoAuthenticationProvider and LdapAuthenticationProvider are compatible with any mechanism which submits a simple username/password authentication request and so will work with form-based logins or HTTP Basic authentication. On the other hand, some authentication mechanisms create an authentication request object which can only be interpreted by a single type of AuthenticationProvider. An example of this would be JA-SIG CAS, which uses the notion of a service ticket and so can therefore only be authenticated by a CasAuthenticationProvider. You needn’t be too concerned about this, because if you forget to register a suitable provider, you’ll simply receive a ProviderNotFoundException when an attempt to authenticate is made.


##### Erasing Credentials on Successful Authentication
By default (from Spring Security 3.1 onwards) the ProviderManager will attempt to clear any sensitive credentials information from the Authentication object which is returned by a successful authentication request. This prevents information like passwords being retained longer than necessary.

This may cause issues when you are using a cache of user objects, for example, to improve performance in a stateless application. If the Authentication contains a reference to an object in the cache (such as a UserDetails instance) and this has its credentials removed, then it will no longer be possible to authenticate against the cached value. You need to take this into account if you are using a cache. An obvious solution is to make a copy of the object first, either in the cache implementation or in the AuthenticationProvider which creates the returned Authentication object. Alternatively, you can disable the eraseCredentialsAfterAuthentication property on ProviderManager. See the Javadoc for more information.

##### DaoAuthenticationProvider

The simplest AuthenticationProvider implemented by Spring Security is DaoAuthenticationProvider.

It leverages a UserDetailsService (as a DAO) in order to lookup the username, password and GrantedAuthority s. It authenticates the user simply by comparing the password submitted in a UsernamePasswordAuthenticationToken against the one loaded by the UserDetailsService.
```xml
<bean id="daoAuthenticationProvider"
	       class="org.springframework.security.authentication.dao.DaoAuthenticationProvider">
<property name="userDetailsService" ref="inMemoryDaoImpl"/>
<property name="passwordEncoder" ref="passwordEncoder"/>
</bean>
```
The PasswordEncoder is optional. A PasswordEncoder provides encoding and decoding of passwords presented in the UserDetails object that is returned from the configured UserDetailsService.

---

### UserDetailsService Implementations
most authentication providers take advantage of the UserDetails and UserDetailsService interfaces. Recall that the contract for UserDetailsService is a single method:
```java
UserDetails loadUserByUsername(String username) throws UsernameNotFoundException;
```
The returned UserDetails is an interface that provides getters that guarantee non-null provision of authentication information.

Given UserDetailsService is so simple to implement, it should be easy for users to retrieve authentication information using a persistence strategy of their choice. Having said that, Spring Security does include a couple of useful base implementations, which we’ll look at below.

##### In-Memory Authentication
内存型,一般用于简单的用户。
```xml
<user-service id="userDetailsService">
	<!-- Password is prefixed with {noop} to indicate to DelegatingPasswordEncoder that
	NoOpPasswordEncoder should be used. This is not safe for production, but makes reading
	in samples easier. Normally passwords should be hashed using BCrypt -->
	<user name="jimi" password="{noop}jimispassword" authorities="ROLE_USER, ROLE_ADMIN" />
	<user name="bob" password="{noop}bobspassword" authorities="ROLE_USER" />
</user-service>
```
##### JdbcDaoImpl
Spring Security also includes a UserDetailsService that can obtain authentication information from a JDBC data source.
```xml
<bean id="dataSource" class="org.springframework.jdbc.datasource.DriverManagerDataSource">
	<property name="driverClassName" value="org.hsqldb.jdbcDriver"/>
	<property name="url" value="jdbc:hsqldb:hsql://localhost:9001"/>
	<property name="username" value="sa"/>
	<property name="password" value=""/>
</bean>

<bean id="userDetailsService"
	class="org.springframework.security.core.userdetails.jdbc.JdbcDaoImpl">
<property name="dataSource" ref="dataSource"/>
</bean>
```
You can use different relational database management systems by modifying the DriverManagerDataSource shown above. You can also use a global data source obtained from JNDI, as with any other Spring configuration.

By default, JdbcDaoImpl loads the authorities for a single user with the assumption that the authorities are mapped directly to users (see the database schema appendix). An alternative approach is to partition the authorities into groups and assign groups to the user.

---

### Password Encoding
<font color="RED">**will add some demo code later.**</font>

## 4. Web Application Security.
---
Spring Security provides authentication and access-control features for the web layer of an application.

see which classes and interfaces are actually assembled to provide web-layer security.

---

### 1.1 The Security Filter Chain.

 It deals in HttpServletRequest s and HttpServletResponse s and doesn’t care whether the requests come from a browser, a web service client, an HttpInvoker or an AJAX application.

Spring Security maintains a filter chain internally where each of the filters has a particular responsibility and filters are added or removed from the configuration depending on which services are required.

#### 1.2 DelegatingFilterProxy
When using servlet filters, you obviously need to declare them in your web.xml, or they will be ignored by the servlet container.
###### FilterChainProxy
Spring Security’s web infrastructure should only be used by delegating to an instance of FilterChainProxy. The security filters should not be used by themselves.


```xml
<bean id="filterChainProxy" class="org.springframework.security.web.FilterChainProxy">
<constructor-arg>
	<list>
	<sec:filter-chain pattern="/restful/**" filters="
		securityContextPersistenceFilterWithASCFalse,                               1
		basicAuthenticationFilter,
		exceptionTranslationFilter,
		filterSecurityInterceptor" />
	<sec:filter-chain pattern="/**" filters="
		securityContextPersistenceFilterWithASCTrue,                                2
		formLoginFilter,
		exceptionTranslationFilter,
		filterSecurityInterceptor" />
	</list>
</constructor-arg>
</bean>
```
You may have noticed we have declared two SecurityContextPersistenceFilter s in the filter chain (ASC is short for allowSessionCreation, a property of SecurityContextPersistenceFilter). As web services will never present a jsessionid on future requests, creating HttpSession s for such user agents would be wasteful. If you had a high-volume application which required maximum scalability, we recommend you use the approach shown above. For smaller applications, using a single SecurityContextPersistenceFilter (with its default allowSessionCreation as true) would likely be sufficient.

#### 1.3 Filter Ordering

The order that filters are defined in the chain is very important. Irrespective of which filters you are actually using, the order should be as follows:

- ChannelProcessingFilter: because it might need to redirect to a different protocol
- SecurityContextPersistenceFilter: so a SecurityContext can be set up in the SecurityContextHolder at the beginning of a web request, and any changes to the SecurityContext can be copied to the HttpSession when the web request ends (ready for use with the next web request)
- ConcurrentSessionFilter: because it uses the SecurityContextHolder functionality and needs to update the SessionRegistry to reflect ongoing requests from the principal
- Authentication processing mechanisms - UsernamePasswordAuthenticationFilter, CasAuthenticationFilter, BasicAuthenticationFilter etc - so that the SecurityContextHolder can be modified to contain a valid Authentication request token
- The SecurityContextHolderAwareRequestFilter: if you are using it to install a Spring Security aware HttpServletRequestWrapper into your servlet container
- The JaasApiIntegrationFilter: if a JaasAuthenticationToken is in the SecurityContextHolder this will process the FilterChain as the Subject in the JaasAuthenticationToken
- RememberMeAuthenticationFilter: so that if no earlier authentication processing mechanism updated the SecurityContextHolder, and the request presents a cookie that enables remember-me services to take place, a suitable remembered Authentication object will be put there
- AnonymousAuthenticationFilter: so that if no earlier authentication processing mechanism updated the SecurityContextHolder, an anonymous Authentication object will be put there
- ExceptionTranslationFilter: to catch any Spring Security exceptions so that either an HTTP error response can be returned or an appropriate AuthenticationEntryPoint can be launched
- FilterSecurityInterceptor: to protect web URIs and raise exceptions when access is denied


#### 1.4 Request Matching and HttpFirewall

**need more information**

#### Use with other Filter-Based Frameworks
If you’re using some other framework that is also filter-based, then you need to make sure that the Spring Security filters come first. This enables the SecurityContextHolder to be populated in time for use by the other filters.

---
### Core Security Filters

There are some key filters which will always be used in a web application which uses Spring Security.

#### 1.1 FilterSecurityInterceptor
FilterSecurityInterceptor is responsible for handling the security of HTTP resources.

 It requires a reference to an AuthenticationManager and an AccessDecisionManager. It is also supplied with configuration attributes that apply to different HTTP URL requests.

 ```xml
 <bean id="filterSecurityInterceptor"
 	        class="org.springframework.security.web.access.intercept.FilterSecurityInterceptor">
     <property name="authenticationManager" ref="authenticationManager"/>
     <property name="accessDecisionManager" ref="accessDecisionManager"/>
     <property name="securityMetadataSource">
         	<security:filter-security-metadata-source>
         	<security:intercept-url pattern="/secure/super/**" access="ROLE_WE_DONT_HAVE"/>
         	<security:intercept-url pattern="/secure/**" access="ROLE_SUPERVISOR,ROLE_TELLER"/>
         	</security:filter-security-metadata-source>
     </property>
 </bean>
 ```
The FilterSecurityInterceptor can be configured with configuration attributes in two ways.
- The first, which is shown above, is using the <filter-security-metadata-source> namespace element.
- The second option is to write your own SecurityMetadataSource.

 the SecurityMetadataSource is responsible for returning a List<ConfigAttribute> containing all of the configuration attributes associated with a single secure HTTP URL.


 #### 1.2 ExceptionTranslationFilter
The ExceptionTranslationFilter sits above the FilterSecurityInterceptor in the security filter stack. It doesn’t do any actual security enforcement itself, but handles exceptions thrown by the security interceptors and provides suitable and HTTP responses.

```xml
<bean id="exceptionTranslationFilter"
    class="org.springframework.security.web.access.ExceptionTranslationFilter">
<property name="authenticationEntryPoint" ref="authenticationEntryPoint"/>
<property name="accessDeniedHandler" ref="accessDeniedHandler"/>
</bean>

<bean id="authenticationEntryPoint"
    class="org.springframework.security.web.authentication.LoginUrlAuthenticationEntryPoint">
<property name="loginFormUrl" value="/login.jsp"/>
</bean>

<bean id="accessDeniedHandler"
	 class="org.springframework.security.web.access.AccessDeniedHandlerImpl">
<property name="errorPage" value="/accessDenied.htm"/>
</bean>
```
##### 1.2.1 AuthenticationEntryPoint

The AuthenticationEntryPoint will be called if the user requests a secure HTTP resource but they are not authenticated.

An appropriate AuthenticationException or AccessDeniedException will be thrown by a security interceptor further down the call stack, triggering the commence method on the entry point.

The one we’ve used here is LoginUrlAuthenticationEntryPoint, which redirects the request to a different URL (typically a login page).

##### 1.2.2 AccessDeniedHandler

If an AccessDeniedException is thrown and a user has already been authenticated, then this means that an operation has been attempted for which they don’t have enough permissions. In this case, ExceptionTranslationFilter will invoke a second strategy, the AccessDeniedHandler.

By default, an AccessDeniedHandlerImpl is used, which just sends a 403 (Forbidden) response to the client.

It’s also possible to supply a custom AccessDeniedHandler when you’re using the namespace to configure your application. See the namespace appendix for more details.

##### 1.2.3 SavedRequest s and the RequestCache Interface
Another responsibility of ExceptionTranslationFilter responsibilities is to save the current request before invoking the AuthenticationEntryPoint. This allows the request to be restored after the user has authenticated. A typical example would be where the user logs in with a form, and is then redirected to the original URL by the default SavedRequestAwareAuthenticationSuccessHandler.

#### 1.3 SecurityContextPersistenceFilter
this filter has two main tasks. It is responsible for storage of the SecurityContext contents between HTTP requests and for clearing the SecurityContextHolder when a request is completed.

##### 1.3.1 SecurityContextRepository

```java
public interface SecurityContextRepository {

SecurityContext loadContext(HttpRequestResponseHolder requestResponseHolder);

void saveContext(SecurityContext context, HttpServletRequest request,
		HttpServletResponse response);
}
```
The HttpRequestResponseHolder is simply a container for the incoming request and response objects, allowing the implementation to replace these with wrapper classes. The returned contents will be passed to the filter chain.

The default implementation is HttpSessionSecurityContextRepository, which stores the security context as an HttpSession attribute .
The most important configuration parameter for this implementation is the allowSessionCreation property, which defaults to true, thus allowing the class to create a session if it needs one to store the security context for an authenticated user (it won’t create one unless authentication has taken place and the contents of the security context have changed). If you don’t want a session to be created, then you can set this property to false.


#### 1.4 UsernamePasswordAuthenticationFilter
This filter is the most commonly used authentication filter and the one that is most often customized

>There are three stages required to configure it
>- Configure a LoginUrlAuthenticationEntryPoint with the URL of the login page, just as we did above, and set it on the ExceptionTranslationFilter.
>- Implement the login page (using a JSP or MVC controller).
>- Configure an instance of UsernamePasswordAuthenticationFilter in the application context
>- Add the filter bean to your filter chain proxy (making sure you pay attention to the order).

```xml
<bean id="authenticationFilter" class=
        "org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter">
    <property name="authenticationManager" ref="authenticationManager"/>
</bean>
```

##### 1.4.1 Application Flow on Authentication Success and Failure
The filter calls the configured AuthenticationManager to process each authentication request.

The destination following a successful authentication or an authentication failure is controlled by the AuthenticationSuccessHandler and AuthenticationFailureHandler strategy interfaces, respectively.

If authentication is successful, the resulting Authentication object will be placed into the SecurityContextHolder.

The configured AuthenticationSuccessHandler will then be called to either redirect or forward the user to the appropriate destination. By default a SavedRequestAwareAuthenticationSuccessHandler is used, which means that the user will be redirected to the original destination they requested before they were asked to login.

---

### Servlet API integration

#### Servlet 2.5+ Integration

The **HttpServletRequest.getRemoteUser()** will return the result of SecurityContextHolder.getContext().getAuthentication().getName() which is typically the current username.

Knowing if the user is authenticated or not can be useful for determining if certain UI elements should be shown or not.

The **HttpServletRequest.getUserPrincipal()** will return the result of SecurityContextHolder.getContext().getAuthentication().

his means it is an Authentication which is typically an instance of UsernamePasswordAuthenticationToken when using username and password based authentication.

The **HttpServletRequest.isUserInRole(String)** will determine if SecurityContextHolder.getContext().getAuthentication().getAuthorities() contains a GrantedAuthority with the role passed into isUserInRole(String).
```java
boolean isAdmin = httpServletRequest.isUserInRole("ADMIN");
```

#### Servlet 3+ Integration
The **HttpServletRequest.authenticate(HttpServletRequest,HttpServletResponse)** method can be used to ensure that a user is authenticated. If they are not authenticated, the configured AuthenticationEntryPoint will be used to request the user to authenticate (i.e. redirect to the login page).

The HttpServletRequest.login(String,String) method can be used to authenticate the user with the current AuthenticationManager. For example, the following would attempt to authenticate with the username "user" and password "password":
```xml
try {
httpServletRequest.login("user","password");
} catch(ServletException e) {
// fail to authenticate
}
```
It is not necessary to catch the ServletException if you want Spring Security to process the failed authentication attempt.

The **HttpServletRequest.logout()** method can be used to log the current user out.

AsyncContext.start(Runnable)

Async Servlet Support

#### Servlet 3.1+ Integration

The **HttpServletRequest.changeSessionId()** is the default method for protecting against Session Fixation attacks in Servlet 3.1 and higher.


---

### Basic and Digest Authentication

Basic and digest authentication are alternative authentication mechanisms which are popular in web applications. Basic authentication is often used with stateless clients which pass their credentials on each request.

#### 3.1 BasicAuthenticationFilter
BasicAuthenticationFilter is responsible for processing basic authentication credentials presented in HTTP headers.

The standard governing HTTP Basic Authentication is defined by RFC 1945, Section 11, and BasicAuthenticationFilter conforms with this RFC.

##### 3.1.1 Configuration

To implement HTTP Basic Authentication, you need to add a BasicAuthenticationFilter to your filter chain. The application context should contain BasicAuthenticationFilter and its required collaborator:
```xml
<bean id="basicAuthenticationFilter"
        class="org.springframework.security.web.authentication.www.BasicAuthenticationFilter">
    <property name="authenticationManager" ref="authenticationManager"/>
    <property name="authenticationEntryPoint" ref="authenticationEntryPoint"/>
</bean>

<bean id="authenticationEntryPoint"
        class="org.springframework.security.web.authentication.www.BasicAuthenticationEntryPoint">
    <property name="realmName" value="Name Of Your Realm"/>
</bean>
```
The configured AuthenticationManager processes each authentication request. If authentication fails, the configured AuthenticationEntryPoint will be used to retry the authentication process.
Usually you will use the filter in combination with a BasicAuthenticationEntryPoint, which returns a 401 response with a suitable header to retry HTTP Basic authentication. If authentication is successful, the resulting Authentication object will be placed into the SecurityContextHolder as usual.

##### 3.2 DigestAuthenticationFilter
DigestAuthenticationFilter is capable of processing digest authentication credentials presented in HTTP headers.

Digest Authentication attempts to solve many of the weaknesses of Basic authentication, specifically by ensuring credentials are never sent in clear text across the wire. Many user agents support Digest Authentication, including Mozilla Firefox and Internet Explorer.

Digest Authentication is a more attractive option if you need to use unencrypted HTTP (i.e. no TLS/HTTPS) and wish to maximise security of the authentication process. Indeed Digest Authentication is a mandatory requirement for the WebDAV protocol, as noted by RFC 2518 Section 17.1.

You should not use Digest in modern applications because it is not considered secure. The most obvious problem is that you must store your passwords in plaintext, encrypted, or an MD5 format. All of these storage formats are considered insecure. Instead, you should use a one way adaptive password hash (i.e. bCrypt, PBKDF2, SCrypt, etc).

##### 3.2.1 Configuration
To implement HTTP Digest Authentication, it is necessary to define DigestAuthenticationFilter in the filter chain. The application context will need to define the DigestAuthenticationFilter and its required collaborators:
```xml
<bean id="digestFilter" class=
    	   "org.springframework.security.web.authentication.www.DigestAuthenticationFilter">
    <property name="userDetailsService" ref="jdbcDaoImpl"/>
    <property name="authenticationEntryPoint" ref="digestEntryPoint"/>
    <property name="userCache" ref="userCache"/>
</bean>

<bean id="digestEntryPoint" class=
    	   "org.springframework.security.web.authentication.www.DigestAuthenticationEntryPoint">
    <property name="realmName" value="Contacts Realm via Digest Authentication"/>
    <property name="key" value="acegi"/>
    <property name="nonceValiditySeconds" value="10"/>
</bean>
```

The configured UserDetailsService is needed because DigestAuthenticationFilter must have direct access to the clear text password of a user. Digest Authentication will NOT work if you are using encoded passwords in your DAO.

### Remember-Me Authentication
Remember-me or persistent-login authentication refers to web sites being able to remember the identity of a principal between sessions.

This is typically accomplished by sending a cookie to the browser, with the cookie being detected during future sessions and causing automated login to take place.

Spring Security provides the necessary hooks for these operations to take place, and has two concrete remember-me implementations. One uses hashing to preserve the security of cookie-based tokens and the other uses a database or other persistent storage mechanism to store the generated tokens.

#### Simple Hash-Based Token Approach

Note that both implementations require a UserDetailsService. If you are using an authentication provider which doesn’t use a UserDetailsService (for example, the LDAP provider) then it won’t work unless you also have a UserDetailsService bean in your application context.


### Cross Site Request Forgery (CSRF)

CSRF protection is enabled by default with Java Configuration. If you would like to disable CSRF, the corresponding Java configuration can be seen below. Refer to the Javadoc of csrf() for additional customizations in how CSRF protection is configured.
```java
@EnableWebSecurity
public class WebSecurityConfig extends
WebSecurityConfigurerAdapter {

	@Override
	protected void configure(HttpSecurity http) throws Exception {
		http
			.csrf().disable();
	}
}
```


### CORS
CORS must be processed before Spring Security because the pre-flight request will not contain any cookies (i.e. the JSESSIONID). If the request does not contain any cookies and Spring Security is first, the request will determine the user is not authenticated (since there are no cookies in the request) and reject it.

The easiest way to ensure that CORS is handled first is to use the CorsFilter. Users can integrate the CorsFilter with Spring Security by providing a CorsConfigurationSource using the following:
```java
@EnableWebSecurity
public class WebSecurityConfig extends WebSecurityConfigurerAdapter {

	@Override
	protected void configure(HttpSecurity http) throws Exception {
		http
			// by default uses a Bean by the name of corsConfigurationSource
			.cors().and()
			...
	}

	@Bean
	CorsConfigurationSource corsConfigurationSource() {
		CorsConfiguration configuration = new CorsConfiguration();
		configuration.setAllowedOrigins(Arrays.asList("https://example.com"));
		configuration.setAllowedMethods(Arrays.asList("GET","POST"));
		UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
		source.registerCorsConfiguration("/**", configuration);
		return source;
	}
}
```

If you are using Spring MVC’s CORS support, you can omit specifying the CorsConfigurationSource and Spring Security will leverage the CORS configuration provided to Spring MVC.

---
### Security HTTP Response Headers

Spring Security’s support for adding various security headers to the response.

#### 5.1 Default Security Headers

> **more questions will going on if request.**<br>
> **more questions will going on if request.**<br>



### Session Management
HTTP session related functionality is handled by a combination of the SessionManagementFilter and the SessionAuthenticationStrategy interface, which the filter delegates to. Typical usage includes session-fixation protection attack prevention, detection of session timeouts and restrictions on how many sessions an authenticated user may have open concurrently.

#### 7.1 SessionManagementFilter
The SessionManagementFilter checks the contents of the SecurityContextRepository against the current contents of the SecurityContextHolder to determine whether a user has been authenticated during the current request, typically by a non-interactive authentication mechanism, such as pre-authentication or remember-me .



> **more questions will going on if request.**<br>
> **more questions will going on if request.**<br>



### WebSocket Security

#### 8.1 WebSocket Configuration
Spring Security 4.0 has introduced authorization support for WebSockets through the Spring Messaging abstraction. To configure authorization using Java Configuration, simply extend the AbstractSecurityWebSocketMessageBrokerConfigurer and configure the MessageSecurityMetadataSourceRegistry.
```java
@Configuration
public class WebSocketSecurityConfig
      extends AbstractSecurityWebSocketMessageBrokerConfigurer {                          1 2

    protected void configureInbound(MessageSecurityMetadataSourceRegistry messages) {
        messages
                .simpDestMatchers("/user/*").authenticated()                               3
    }
}
```

1. Any inbound CONNECT message requires a valid CSRF token to enforce Same Origin Policy
2. The SecurityContextHolder is populated with the user within the simpUser header attribute for any inbound request.
3. Our messages require the proper authorization. Specifically, any inbound message that starts with "/user/" will require ROLE_USER.

#### 8.2 WebSocket Authentication
WebSockets reuse the same authentication information that is found in the HTTP request when the WebSocket connection was made.

This means that the Principal on the HttpServletRequest will be handed off to WebSockets. If you are using Spring Security, the Principal on the HttpServletRequest is overridden automatically.

#### 8.3 WebSocket Authorization

Spring Security 4.0 has introduced authorization support for WebSockets through the Spring Messaging abstraction. To configure authorization using Java Configuration, simply extend the AbstractSecurityWebSocketMessageBrokerConfigurer and configure the MessageSecurityMetadataSourceRegistry.

```java
@Configuration
public class WebSocketSecurityConfig extends AbstractSecurityWebSocketMessageBrokerConfigurer {

    @Override
    protected void configureInbound(MessageSecurityMetadataSourceRegistry messages) {
        messages
                .nullDestMatcher().authenticated()                                          1
                .simpSubscribeDestMatchers("/user/queue/errors").permitAll()                2
                .simpDestMatchers("/app/**").hasRole("USER")                                3
                .simpSubscribeDestMatchers("/user/**", "/topic/friends/*").hasRole("USER")  4
                .simpTypeMatchers(MESSAGE, SUBSCRIBE).denyAll()                             5
                .anyMessage().denyAll();                                                    6

    }
}
```
1. Any message without a destination (i.e. anything other than Message type of MESSAGE or SUBSCRIBE) will require the user to be authenticated

2. Anyone can subscribe to /user/queue/errors
3. Any message that has a destination starting with "/app/" will be require the user to have the role ROLE_USER
4. Any message that starts with "/user/" or "/topic/friends/" that is of type SUBSCRIBE will require ROLE_USER
5. Any other message of type MESSAGE or SUBSCRIBE is rejected. Due to 6 we do not need this step, but it illustrates how one can match on specific message types.
6. Any other Message is rejected. This is a good idea to ensure that you do not miss any messages.

##### 8.3.1  WebSocket Authorization Notes

In order to properly secure your application it is important to understand Spring’s WebSocket support.

**WebSocket Authorization on Message Types**

It is important to understand the distinction between SUBSCRIBE and MESSAGE types of messages and how it works within Spring.

Consider a chat application.

The system can send notifications MESSAGE to all users through a destination of "/topic/system/notifications"
- Clients can receive notifications by SUBSCRIBE to the "/topic/system/notifications".
- While we want clients to be able to SUBSCRIBE to "/topic/system/notifications", we do not want to enable them to send a MESSAGE to that destination. If we allowed sending a MESSAGE to "/topic/system/notifications", then clients could send a message directly to that endpoint and impersonate the system.


In general, it is common for applications to deny any MESSAGE sent to a message that starts with the broker prefix (i.e. "/topic/" or "/queue/").

---


[1]:https://docs.spring.io/spring-security/site/docs/5.0.4.BUILD-SNAPSHOT/reference/htmlsingle/#secure-objects

[2]:https://docs.spring.io/spring-security/site/docs/5.0.4.BUILD-SNAPSHOT/reference/htmlsingle/images/security-interception.png
